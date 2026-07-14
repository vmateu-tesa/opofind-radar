import os
import re
import time
from datetime import datetime, date
from zoneinfo import ZoneInfo
from html import escape as html_escape
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from bs4 import BeautifulSoup

from fastapi import FastAPI, Depends, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from pydantic import BaseModel

from db.database import init_db, get_session
from db.models import Convocatoria, Notificacion, AvisoPlazo, MunicipioFavorito, Vigilancia
from core.matcher import Matcher
from core.classifier import classify_tipo
from core import plazos
from core import geo
from config import vigilancias as vigilancias_cfg
from scrapers.dip_otras_oposiciones import DipOtrasOposicionesScraper
from scrapers.dip_bolsa_oferta import DipBolsaOfertaScraper
from scrapers.boe import BoeScraper
from scrapers.benidorm import BenidormScraper
from scrapers.dogv import DogvScraper
from scrapers.bop_alicante import BopAlicanteScraper
from scrapers.elche import ElcheScraper
from scrapers.gestiona import GestionaScraper
from scrapers.alfaz import AlfazScraper
from scrapers.villajoyosa import VillajoyosaScraper
from notifications.telegram_bot import TelegramNotifier
from notifications.whatsapp_api import WhatsappNotifier
from notifications.email_smtp import EmailNotifier
from study_module.generator import StudyGenerator


def _env_int(nombre, defecto):
    try:
        return int(os.getenv(nombre, str(defecto)))
    except (TypeError, ValueError):
        return defecto


def _canales_activos():
    """Instancia los notificadores cuyo canal esta habilitado por env
    (ENABLE_TELEGRAM/ENABLE_WHATSAPP/ENABLE_EMAIL == '1'). Devuelve lista de
    (nombre_canal, notificador)."""
    canales = []
    if os.getenv("ENABLE_TELEGRAM") == "1":
        canales.append(("telegram", TelegramNotifier()))
    if os.getenv("ENABLE_WHATSAPP") == "1":
        canales.append(("whatsapp", WhatsappNotifier()))
    if os.getenv("ENABLE_EMAIL") == "1":
        canales.append(("email", EmailNotifier()))
    return canales


def _linea_plazo(fecha_inicio, fecha_fin) -> str:
    """Linea de texto legible sobre el estado del plazo, para los mensajes de
    alerta. Vacia si no hay fechas."""
    estado = plazos.estado_plazo(fecha_inicio, fecha_fin)
    if estado == plazos.SIN_FECHAS:
        return ""
    if estado == plazos.PROXIMAMENTE:
        return f"<b>Plazo:</b> abre el {html_escape(str(fecha_inicio))}"
    if estado == plazos.CERRADO:
        return f"<b>Plazo:</b> {html_escape(str(fecha_fin))} (cerrado)"
    dias = plazos.dias_restantes(fecha_fin)
    if dias == 0:
        cola = "¡ULTIMO DIA hoy!"
    elif dias and dias > 0:
        cola = f"quedan {dias} dias"
    else:
        cola = ""
    rango = " - ".join(x for x in [str(fecha_inicio or ""), str(fecha_fin or "")] if x)
    return f"<b>Plazo:</b> {html_escape(rango)} ({cola})" if cola else f"<b>Plazo:</b> {html_escape(rango)}"

def _clean_for_telegram(text: str) -> str:
    """Limpia HTML crudo que puede venir de un RSS (p.ej. observaciones de
    dip_bolsa_oferta trae <strong>/<br/> tal cual) y escapa caracteres
    especiales, para que el texto sea seguro dentro de un mensaje de
    Telegram con parse_mode="HTML" -- que solo admite un subconjunto muy
    limitado de etiquetas (<b>, <i>, <a>...), no <strong> ni <br/>. Sin este
    paso Telegram rechaza el mensaje ENTERO con un 400 si el texto trae
    markup no soportado, y la notificacion no llega."""
    if not text:
        return text
    texto = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    texto = BeautifulSoup(texto, "html.parser").get_text()
    return html_escape(texto)


def check_updates():
    print(f"[{datetime.now()}] Iniciando chequeo de OpoRadar...")
    session = get_session()
    matcher = Matcher()

    # Canales de aviso activos (telegram/whatsapp/email segun ENABLE_*).
    canales = _canales_activos()

    # Municipios favoritos del usuario (una sola query por ejecucion):
    # cualquier novedad de un municipio favorito avisa SIEMPRE, coincida o
    # no con los perfiles de alertas.yaml.
    favoritos = {m.nombre for m in session.query(MunicipioFavorito).all()}

    scrapers = [
        DipOtrasOposicionesScraper(),
        DipBolsaOfertaScraper(),
        BoeScraper(),            # provincia de Alicante, ultimos 30 dias
        BenidormScraper(),
        DogvScraper(),           # provincia de Alicante
        BopAlicanteScraper(dias_atras=_env_int("BOP_DIAS_ATRAS", 3)),
        ElcheScraper(),          # tablon RRHH del Ayto de Elche
        GestionaScraper(),       # tablones Marina Baixa (la Nucia, Altea, ...)
        AlfazScraper(),          # tablon de seleccion de personal de l'Alfas del Pi
        VillajoyosaScraper(),    # ofertas de empleo del Ayto de la Vila Joiosa
    ]

    todas_convocatorias = []
    for s in scrapers:
        try:
            res = s.scrape()
            todas_convocatorias.extend(res)
            print(f"Scraper {s.__class__.__name__}: {len(res)} resultados.")
        except Exception as e:
            print(f"Error ejecutando scraper {s.__class__.__name__}: {e}")
            
    seen_ids = set()
    
    for c_data in todas_convocatorias:
        if c_data.id_origen in seen_ids:
            continue
        seen_ids.add(c_data.id_origen)
        
        nuevo_hash = c_data.calculate_hash()
        conv = session.query(Convocatoria).filter_by(id=c_data.id_origen).first()
        
        estado = None
        if not conv:
            conv = Convocatoria(
                id=c_data.id_origen,
                fuente=c_data.fuente,
                titulo=c_data.titulo,
                entidad=c_data.entidad,
                enlace=c_data.enlace,
                hash_contenido=nuevo_hash,
                fecha_inicio=c_data.fecha_inicio,
                fecha_fin=c_data.fecha_fin,
                observaciones=c_data.observaciones,
                vacantes=c_data.vacantes,
                estado="nuevo",
                tipo=classify_tipo(c_data.titulo, c_data.observaciones),
            )
            session.add(conv)
            estado = "NUEVA"
        elif conv.hash_contenido != nuevo_hash:
            conv.hash_contenido = nuevo_hash
            conv.observaciones = c_data.observaciones
            conv.vacantes = c_data.vacantes
            conv.estado = "actualizado"
            conv.tipo = classify_tipo(c_data.titulo, c_data.observaciones)
            estado = "ACTUALIZACIÓN"

        if estado:
            texto_busqueda = f"{c_data.titulo} {c_data.entidad} {c_data.observaciones}"
            perfiles_matched = matcher.match(texto_busqueda)

            # Municipio favorito: si la oferta pertenece a un municipio
            # marcado por el usuario, avisa aunque no matchee ningun perfil.
            muni = geo.municipio_de(c_data.entidad or "", c_data.titulo or "")
            muni_favorito = muni if muni in favoritos else None

            # Si el usuario ha marcado esta convocatoria para seguimiento
            # manual, cualquier actualizacion avisa SIEMPRE, aunque no
            # coincida con ningun perfil de alertas.yaml.
            if perfiles_matched or conv.seguimiento or muni_favorito:
                motivos = list(perfiles_matched)
                if conv.seguimiento and not perfiles_matched:
                    motivos.append('seguimiento manual')
                if muni_favorito:
                    motivos.append(f'municipio favorito: {muni_favorito}')
                print(f"Match encontrado ({', '.join(motivos)}): [{estado}] {c_data.titulo} en {c_data.entidad}")

                msg = f"🚨 <b>{estado} Oposición/Empleo</b>\n"
                if conv.seguimiento and not perfiles_matched:
                    msg += "<b>(Convocatoria en seguimiento)</b>\n"
                if muni_favorito:
                    msg += f"📍 <b>Municipio favorito:</b> {html_escape(muni_favorito)}\n"
                if perfiles_matched:
                    msg += f"<b>Perfiles:</b> {html_escape(', '.join(perfiles_matched))}\n"
                msg += f"<b>Entidad:</b> {_clean_for_telegram(c_data.entidad)}\n"
                msg += f"<b>Plaza:</b> {_clean_for_telegram(c_data.titulo)}\n"
                if c_data.vacantes:
                    msg += f"<b>Vacantes:</b> {_clean_for_telegram(c_data.vacantes)}\n"
                linea_plazo = _linea_plazo(c_data.fecha_inicio, c_data.fecha_fin)
                if linea_plazo:
                    msg += linea_plazo + "\n"
                if c_data.enlace:
                    # El enlace va como texto plano (no <a href>): puede traer
                    # caracteres que romperian el atributo href sin escapar aparte.
                    msg += f"<b>Enlace:</b> {html_escape(c_data.enlace)}\n"
                if c_data.observaciones:
                    msg += f"<b>Obs:</b> {_clean_for_telegram(c_data.observaciones)}\n"

                for nombre_canal, notificador in canales:
                    try:
                        if notificador.send_message(msg):
                            session.add(Notificacion(
                                convocatoria_id=conv.id,
                                hash_enviado=nuevo_hash,
                                canal=nombre_canal,
                            ))
                    except Exception as e:
                        print(f"Error notificando por {nombre_canal}: {e}")

    session.commit()

    # Segunda pasada: avisos de PLAZO (apertura y recordatorios de cierre) de
    # las convocatorias seguidas o que matchean algun perfil.
    try:
        revisar_plazos(session, matcher, canales)
    except Exception as e:
        print(f"Error revisando plazos: {e}")

    # Tercera pasada: vigilancias dirigidas (plazas concretas que el usuario
    # sigue de forma fija). Tarea especifica del cron: comprueba cada dia si
    # alguna de esas plazas ya se ha convocado y avisa el primero.
    try:
        revisar_vigilancias(session, canales)
    except Exception as e:
        print(f"Error revisando vigilancias: {e}")

    session.close()
    print(f"[{datetime.now()}] Chequeo finalizado.")


def sincronizar_vigilancias(session):
    """Vuelca las vigilancias declaradas en config/vigilancias.py a la tabla
    (upsert por slug). Crea las que falten y refresca sus metadatos, pero NO
    toca el estado ni la deteccion ya registrada. Asi las vigilancias son
    'fijas': aparecen en la app desde el arranque, sin esperar al cron."""
    for cfg in vigilancias_cfg.VIGILANCIAS:
        fila = session.query(Vigilancia).filter_by(slug=cfg["slug"]).first()
        if fila is None:
            fila = Vigilancia(slug=cfg["slug"], estado="vigilando")
            session.add(fila)
        fila.titulo = cfg.get("titulo", cfg["slug"])
        fila.entidad = cfg.get("entidad")
        fila.municipio = cfg.get("municipio")
        fila.enlace = cfg.get("enlace")
        fila.notas = cfg.get("notas")
    session.commit()


def revisar_vigilancias(session, canales):
    """Tarea especifica del cron: para cada vigilancia que sigue en estado
    'vigilando', busca entre las convocatorias almacenadas alguna que encaje
    con sus reglas (config/vigilancias.py). Si la encuentra, la marca como
    'detectada', pone esa convocatoria en seguimiento y envia un aviso
    PRIORITARIO por todos los canales -- para enterarse el primero."""
    sincronizar_vigilancias(session)

    convs = None  # se carga perezosamente solo si hay algo que vigilar
    for cfg in vigilancias_cfg.VIGILANCIAS:
        fila = session.query(Vigilancia).filter_by(slug=cfg["slug"]).first()
        if fila is None or fila.estado == "detectada":
            continue
        if convs is None:
            convs = session.query(Convocatoria).all()

        for c in convs:
            muni = geo.municipio_de(c.entidad or "", c.titulo or "")
            if not vigilancias_cfg.coincide(cfg, c.titulo or "", c.entidad or "",
                                            c.observaciones or "", muni or ""):
                continue

            fila.estado = "detectada"
            fila.convocatoria_id = c.id
            fila.detectada_at = datetime.utcnow()
            c.seguimiento = True  # queda seguida para futuros cambios tambien
            print(f"VIGILANCIA DETECTADA [{cfg['slug']}]: {c.titulo} en {c.entidad}")

            msg = "🎯 <b>¡PLAZA VIGILADA DETECTADA!</b>\n"
            msg += f"<b>{_clean_for_telegram(cfg.get('titulo', ''))}</b>\n"
            msg += f"<b>Plaza:</b> {_clean_for_telegram(c.titulo or '')}\n"
            msg += f"<b>Entidad:</b> {_clean_for_telegram(c.entidad or '')}\n"
            linea_plazo = _linea_plazo(c.fecha_inicio, c.fecha_fin)
            if linea_plazo:
                msg += linea_plazo + "\n"
            if c.enlace:
                msg += f"<b>Enlace:</b> {html_escape(c.enlace)}\n"

            for nombre_canal, notificador in canales:
                try:
                    notificador.send_message(msg)
                except Exception as e:
                    print(f"Error avisando vigilancia por {nombre_canal}: {e}")
            break

    session.commit()


def revisar_plazos(session, matcher, canales, hoy=None):
    """Recorre las convocatorias con seguimiento=True, que matchean algun
    perfil o que son de un municipio favorito, y envia los avisos de plazo
    que toquen HOY (apertura / cierre en N dias), registrando cada uno en
    AvisoPlazo para no repetirlo.

    Anti-spam: si en una misma ejecucion tocan mas de 5 avisos, se agrupan en
    un unico mensaje-resumen por canal en vez de enviar uno por uno."""
    if hoy is None:
        hoy = date.today()

    candidatas = session.query(Convocatoria).filter(
        (Convocatoria.fecha_fin.isnot(None)) | (Convocatoria.fecha_inicio.isnot(None))
    ).all()

    favoritos = {m.nombre for m in session.query(MunicipioFavorito).all()}

    pendientes = []  # (conv, tipo_aviso)
    for conv in candidatas:
        texto = f"{conv.titulo} {conv.entidad} {conv.observaciones or ''}"
        if not conv.seguimiento and not matcher.match(texto):
            muni = geo.municipio_de(conv.entidad or "", conv.titulo or "")
            if not (muni and muni in favoritos):
                continue
        ya = {a.tipo_aviso for a in session.query(AvisoPlazo).filter_by(convocatoria_id=conv.id).all()}
        for aviso in plazos.avisos_pendientes(conv, ya, plazos.leer_umbrales(), hoy=hoy):
            pendientes.append((conv, aviso))

    if not pendientes:
        return

    def _msg_individual(conv, aviso):
        if aviso == plazos.AVISO_APERTURA:
            cabecera = "⏰ <b>PLAZO ABIERTO</b>"
        else:
            dias = plazos.dias_restantes(conv.fecha_fin, hoy=hoy)
            cabecera = ("🔔 <b>ULTIMO DIA de plazo</b>" if dias == 0
                        else f"🔔 <b>EL PLAZO CIERRA EN {dias} DIAS</b>")
        m = cabecera + "\n"
        m += f"<b>Entidad:</b> {_clean_for_telegram(conv.entidad or '')}\n"
        m += f"<b>Plaza:</b> {_clean_for_telegram(conv.titulo or '')}\n"
        linea = _linea_plazo(conv.fecha_inicio, conv.fecha_fin)
        if linea:
            m += linea + "\n"
        if conv.enlace:
            m += f"<b>Enlace:</b> {html_escape(conv.enlace)}\n"
        return m

    # Envio (individual si son pocos, agrupado si son muchos).
    if len(pendientes) > 5:
        lineas = []
        for conv, aviso in pendientes:
            dias = plazos.dias_restantes(conv.fecha_fin, hoy=hoy)
            cola = "abre" if aviso == plazos.AVISO_APERTURA else (
                "ULTIMO DIA" if dias == 0 else f"cierra, quedan {dias} dias")
            lineas.append(f"• {_clean_for_telegram(conv.titulo or '')} ({_clean_for_telegram(conv.entidad or '')}): {cola}")
        resumen = "⏰ <b>Avisos de plazo</b>\n" + "\n".join(lineas)
        for nombre_canal, notificador in canales:
            try:
                notificador.send_message(resumen)
            except Exception as e:
                print(f"Error aviso-plazo (resumen) por {nombre_canal}: {e}")
    else:
        for conv, aviso in pendientes:
            m = _msg_individual(conv, aviso)
            for nombre_canal, notificador in canales:
                try:
                    notificador.send_message(m)
                except Exception as e:
                    print(f"Error aviso-plazo por {nombre_canal}: {e}")

    # Solo se marcan como enviados si habia al menos un canal al que
    # intentar mandarlos. Si no hay ningun canal configurado todavia, se
    # dejan pendientes: asi, cuando el usuario configure Telegram/email,
    # recibira los avisos de los plazos que sigan abiertos (agrupados si son
    # muchos), en vez de haberselos perdido en silencio.
    if canales:
        for conv, aviso in pendientes:
            session.add(AvisoPlazo(convocatoria_id=conv.id, tipo_aviso=aviso))
        session.commit()

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    interval_hours = int(os.getenv("INTERVAL_HOURS", "0") or "0")
    if interval_hours > 0:
        scheduler.add_job(check_updates, IntervalTrigger(hours=interval_hours))
    else:
        # Por defecto, una vez al dia a las 4:00 hora de Madrid (estas
        # fuentes no cambian varias veces al dia, no hace falta sondear mas
        # a menudo). Zona horaria EXPLICITA: el contenedor corre en UTC por
        # defecto (sin esto, "hour=4" disparaba a las 4:00 UTC = 6:00 en
        # Madrid en verano -- 2h tarde respecto a lo pedido). zoneinfo
        # maneja el cambio de horario CET/CEST automaticamente.
        scheduler.add_job(check_updates, CronTrigger(hour=4, minute=0, timezone=ZoneInfo("Europe/Madrid")))
    scheduler.start()
    yield
    scheduler.shutdown()

load_dotenv()
init_db()

# Deja las vigilancias declaradas (config/vigilancias.py) reflejadas en la
# BD desde el arranque, para que aparezcan en la app aunque el cron no haya
# corrido todavia tras el despliegue.
try:
    _sesion_arranque = get_session()
    sincronizar_vigilancias(_sesion_arranque)
    _sesion_arranque.close()
except Exception as e:
    print(f"Error sincronizando vigilancias al arranque: {e}")

app = FastAPI(lifespan=lifespan, title="OpoRadar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # no hay cookies/sesion; "*" + credenciales no es valido igualmente
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

# Rate limiting minimo en memoria para los endpoints caros/con efectos
# (evita que un doble-click, un bucle del frontend, o un bot que encuentre
# la URL puedan disparar scrapes repetidos o quemar la cuota de Gemini).
# No hay sistema de login en esta app (el frontend es de un unico usuario),
# asi que una API key rompería su propio uso; esto es una cota barata, no
# autenticacion real -- si esta app se expone mas alla de la red privada del
# usuario, conviene ademas restringir el acceso a nivel de infraestructura.
_last_call: dict[str, float] = {}


def _rate_limit(key: str, min_interval_seconds: float):
    now = time.monotonic()
    last = _last_call.get(key, 0.0)
    remaining = min_interval_seconds - (now - last)
    if remaining > 0:
        raise HTTPException(status_code=429, detail=f"Espera {int(remaining) + 1}s antes de repetir esta accion.")
    _last_call[key] = now


@app.get("/api/estado")
def estado(db: Session = Depends(get_db)):
    """Estado del radar para la interfaz: que canales de aviso estan activos
    (booleanos, nunca secretos), proxima ejecucion programada y algunos
    contadores. Sirve para avisar en el frontend si NO hay ningun canal
    configurado (las alertas no llegarian a ningun sitio)."""
    def _tel_ok():
        return os.getenv("ENABLE_TELEGRAM") == "1" and bool(os.getenv("TELEGRAM_TOKEN")) and bool(os.getenv("TELEGRAM_CHAT_ID"))

    def _wa_ok():
        return os.getenv("ENABLE_WHATSAPP") == "1" and bool(os.getenv("WHATSAPP_TOKEN")) and bool(os.getenv("WHATSAPP_PHONE_ID"))

    def _email_ok():
        return os.getenv("ENABLE_EMAIL") == "1" and bool(os.getenv("SMTP_HOST")) and bool(os.getenv("EMAIL_TO") or os.getenv("SMTP_USER"))

    proxima = None
    try:
        jobs = scheduler.get_jobs()
        if jobs and jobs[0].next_run_time:
            proxima = jobs[0].next_run_time.isoformat()
    except Exception:
        proxima = None

    return {
        "canales": {"telegram": _tel_ok(), "whatsapp": _wa_ok(), "email": _email_ok()},
        "proxima_ejecucion": proxima,
        "total_convocatorias": db.query(Convocatoria).count(),
        "seguidas": db.query(Convocatoria).filter_by(seguimiento=True).count(),
        "municipios_favoritos": db.query(MunicipioFavorito).count(),
        "vigilancias": db.query(Vigilancia).count(),
        "vigilancias_detectadas": db.query(Vigilancia).filter_by(estado="detectada").count(),
    }


def _conv_a_dict(c: Convocatoria) -> dict:
    """Serializa una convocatoria añadiendo los campos CALCULADOS que
    necesita el cuadro de mando: estado del plazo hoy, dias restantes y
    municipio canonico. Se calculan en servidor para que frontend y motor de
    avisos usen exactamente la misma logica (core/plazos y core/geo), sin
    duplicarla en JavaScript."""
    d = {col.name: getattr(c, col.name) for col in Convocatoria.__table__.columns}
    d["plazo_estado"] = plazos.estado_plazo(c.fecha_inicio, c.fecha_fin)
    d["dias_restantes"] = plazos.dias_restantes(c.fecha_fin)
    d["municipio"] = geo.municipio_de(c.entidad or "", c.titulo or "")
    return d


@app.get("/api/convocatorias")
def read_convocatorias(db: Session = Depends(get_db)):
    # Retornar convocatorias ordenadas por fecha descendente. El frontend
    # carga todo de una vez y filtra en cliente (no hay paginacion en la
    # interfaz), asi que el limite es solo una cota de seguridad, no una
    # pagina real. Con 10 fuentes activas el total ya supera facilmente los
    # 500 registros (el limite anterior); 2000 da margen para bastantes
    # meses de acumulacion antes de necesitar paginacion de verdad.
    filas = db.query(Convocatoria).order_by(Convocatoria.fecha_publicacion.desc()).limit(2000).all()
    return [_conv_a_dict(c) for c in filas]


class MunicipioIn(BaseModel):
    nombre: str


@app.get("/api/municipios")
def read_municipios(db: Session = Depends(get_db)):
    """Todos los municipios canonicos de la provincia con contadores sobre
    las convocatorias almacenadas (total y con plazo abierto), y si son
    favoritos. Es la base del selector de favoritos del frontend."""
    favoritos = {m.nombre for m in db.query(MunicipioFavorito).all()}
    contadores = {}  # canonico -> [total, abiertas]
    for c in db.query(Convocatoria).all():
        muni = geo.municipio_de(c.entidad or "", c.titulo or "")
        if not muni:
            continue
        par = contadores.setdefault(muni, [0, 0])
        par[0] += 1
        if plazos.estado_plazo(c.fecha_inicio, c.fecha_fin) in (plazos.ABIERTO, plazos.CIERRA_PRONTO):
            par[1] += 1
    return [
        {
            "nombre": m,
            "favorito": m in favoritos,
            "total": contadores.get(m, [0, 0])[0],
            "abiertas": contadores.get(m, [0, 0])[1],
        }
        for m in geo.lista_municipios()
    ]


@app.get("/api/vigilancias")
def read_vigilancias(db: Session = Depends(get_db)):
    """Vigilancias dirigidas del usuario (plazas fijas que se buscan cada dia
    en el cron). Devuelve su estado y, si ya se detecto la convocatoria, sus
    datos (plazo incluido) para poder enlazarla desde la interfaz."""
    filas = db.query(Vigilancia).order_by(Vigilancia.creado_at).all()
    salida = []
    for v in filas:
        conv = None
        if v.convocatoria_id:
            c = db.query(Convocatoria).filter_by(id=v.convocatoria_id).first()
            if c:
                conv = {
                    "id": c.id,
                    "titulo": c.titulo,
                    "enlace": c.enlace,
                    "fecha_inicio": c.fecha_inicio,
                    "fecha_fin": c.fecha_fin,
                    "plazo_estado": plazos.estado_plazo(c.fecha_inicio, c.fecha_fin),
                    "dias_restantes": plazos.dias_restantes(c.fecha_fin),
                }
        salida.append({
            "slug": v.slug,
            "titulo": v.titulo,
            "entidad": v.entidad,
            "municipio": v.municipio,
            "enlace": v.enlace,
            "notas": v.notas,
            "estado": v.estado,
            "detectada_at": v.detectada_at.isoformat() if v.detectada_at else None,
            "convocatoria": conv,
        })
    return salida


@app.get("/api/municipios-favoritos")
def read_municipios_favoritos(db: Session = Depends(get_db)):
    return [
        {"id": m.id, "nombre": m.nombre}
        for m in db.query(MunicipioFavorito).order_by(MunicipioFavorito.nombre).all()
    ]


@app.post("/api/municipios-favoritos")
def add_municipio_favorito(payload: MunicipioIn, db: Session = Depends(get_db)):
    """Marca un municipio como favorito. El nombre se resuelve al canonico
    sin distinguir mayusculas/acentos/variantes ("elx" -> "Elche").
    Idempotente: repetir un favorito devuelve el existente, no un error."""
    canonico = geo.resolver_municipio(payload.nombre)
    if not canonico:
        raise HTTPException(
            status_code=400,
            detail=f"'{payload.nombre}' no es un municipio de la provincia de Alicante",
        )
    existente = db.query(MunicipioFavorito).filter_by(nombre=canonico).first()
    if existente:
        return {"id": existente.id, "nombre": existente.nombre}
    fav = MunicipioFavorito(nombre=canonico)
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return {"id": fav.id, "nombre": fav.nombre}


@app.delete("/api/municipios-favoritos/{nombre}")
def del_municipio_favorito(nombre: str, db: Session = Depends(get_db)):
    canonico = geo.resolver_municipio(nombre) or nombre
    fav = db.query(MunicipioFavorito).filter_by(nombre=canonico).first()
    if not fav:
        raise HTTPException(status_code=404, detail=f"'{nombre}' no estaba en favoritos")
    db.delete(fav)
    db.commit()
    return {"ok": True, "nombre": canonico}

@app.post("/api/convocatorias/{convocatoria_id}/seguir")
def seguir_convocatoria(convocatoria_id: str, db: Session = Depends(get_db)):
    """Marca una convocatoria para seguimiento manual: a partir de ahora,
    cualquier actualizacion suya (el hash de contenido cambia -- nueva
    publicacion en Obs, cambio de fechas, etc.) dispara notificacion
    SIEMPRE, coincida o no con los perfiles de alertas.yaml."""
    conv = db.query(Convocatoria).filter_by(id=convocatoria_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
    conv.seguimiento = True
    db.commit()
    return {"id": conv.id, "seguimiento": True}

@app.post("/api/convocatorias/{convocatoria_id}/dejar-de-seguir")
def dejar_de_seguir_convocatoria(convocatoria_id: str, db: Session = Depends(get_db)):
    conv = db.query(Convocatoria).filter_by(id=convocatoria_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Convocatoria no encontrada")
    conv.seguimiento = False
    db.commit()
    return {"id": conv.id, "seguimiento": False}

@app.post("/api/trigger-sync")
def trigger_sync(background_tasks: BackgroundTasks):
    _rate_limit("trigger-sync", 300)  # maximo una sincronizacion manual cada 5 minutos
    background_tasks.add_task(check_updates)
    return {"message": "Sincronización manual iniciada en segundo plano"}

@app.post("/api/generar-estudio/{convocatoria_id}")
def generar_estudio(convocatoria_id: str, db: Session = Depends(get_db)):
    _rate_limit("ia", 10)  # evita rafagas contra la API de Gemini
    conv = db.query(Convocatoria).filter_by(id=convocatoria_id).first()
    if not conv:
        return {"error": "Convocatoria no encontrada"}
    if conv.tipo != "convocatoria":
        # Listas de admitidos, nombramientos, etc. no son un proceso
        # selectivo abierto: no tiene sentido generar temario para ellos
        # (ni gastar cuota de Gemini en contenido sin utilidad real).
        return {"error": "Esta publicación no es un proceso selectivo abierto (es de tipo "
                          f"'{conv.tipo}'); no se genera temario para ella."}

    study = StudyGenerator()
    texto_base = f"{conv.titulo} {conv.observaciones} en {conv.entidad}"
    temario = study.generate_syllabus(texto_base)

    return {"temario": temario}

@app.post("/api/generar-test/{convocatoria_id}")
def generar_test(convocatoria_id: str, db: Session = Depends(get_db)):
    _rate_limit("ia", 10)  # evita rafagas contra la API de Gemini
    conv = db.query(Convocatoria).filter_by(id=convocatoria_id).first()
    if not conv:
        return {"error": "Convocatoria no encontrada"}
    if conv.tipo != "convocatoria":
        return {"error": "Esta publicación no es un proceso selectivo abierto (es de tipo "
                          f"'{conv.tipo}'); no se genera test para ella."}

    study = StudyGenerator()
    texto_base = f"{conv.titulo} {conv.observaciones} en {conv.entidad}"
    test_json = study.generate_test(texto_base)
    
    # Intenta parsear el JSON para devolverlo estructurado
    import json
    try:
        data = json.loads(test_json)
        return data
    except Exception as e:
        # Fallback por si la IA devuelve algo raro
        return {"error": "JSON Parsing failed", "raw": test_json}

if __name__ == "__main__":
    import uvicorn
    # Para desarrollo, ejecutamos con reload
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
