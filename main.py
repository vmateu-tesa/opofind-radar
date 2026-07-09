import os
from datetime import datetime
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from db.database import init_db, get_session
from db.models import Convocatoria, Notificacion
from core.matcher import Matcher
from scrapers.dip_otras_oposiciones import DipOtrasOposicionesScraper
from scrapers.dip_bolsa_oferta import DipBolsaOfertaScraper
from scrapers.boe import BoeScraper
from scrapers.benidorm import BenidormScraper
from scrapers.dogv import DogvScraper
from notifications.telegram_bot import TelegramNotifier
from notifications.whatsapp_api import WhatsappNotifier
from study_module.generator import StudyGenerator

def check_updates():
    print(f"[{datetime.now()}] Iniciando chequeo de OpoRadar...")
    session = get_session()
    matcher = Matcher()
    
    telegram = TelegramNotifier()
    whatsapp = WhatsappNotifier()
    
    scrapers = [
        DipOtrasOposicionesScraper(),
        DipBolsaOfertaScraper(),
        BoeScraper(),
        BenidormScraper(),
        DogvScraper()
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
                estado="nuevo"
            )
            session.add(conv)
            estado = "NUEVA"
        elif conv.hash_contenido != nuevo_hash:
            conv.hash_contenido = nuevo_hash
            conv.observaciones = c_data.observaciones
            conv.vacantes = c_data.vacantes
            conv.estado = "actualizado"
            estado = "ACTUALIZACIÓN"
            
        if estado:
            texto_busqueda = f"{c_data.titulo} {c_data.entidad} {c_data.observaciones}"
            perfiles_matched = matcher.match(texto_busqueda)
            
            if perfiles_matched:
                print(f"Match encontrado ({', '.join(perfiles_matched)}): [{estado}] {c_data.titulo} en {c_data.entidad}")
                
                msg = f"🚨 <b>{estado} Oposición/Empleo</b>\n"
                msg += f"<b>Perfiles:</b> {', '.join(perfiles_matched)}\n"
                msg += f"<b>Entidad:</b> {c_data.entidad}\n"
                msg += f"<b>Plaza:</b> {c_data.titulo}\n"
                if c_data.vacantes:
                    msg += f"<b>Vacantes:</b> {c_data.vacantes}\n"
                if c_data.enlace:
                    msg += f"<b>Enlace:</b> {c_data.enlace}\n"
                if c_data.observaciones:
                    msg += f"<b>Obs:</b> {c_data.observaciones}\n"
                    
                enviado_tg = telegram.send_message(msg) if os.getenv("ENABLE_TELEGRAM") == "1" else False
                enviado_wa = whatsapp.send_message(msg) if os.getenv("ENABLE_WHATSAPP") == "1" else False
                
                if enviado_tg or enviado_wa:
                    notif = Notificacion(
                        convocatoria_id=conv.id,
                        hash_enviado=nuevo_hash,
                        canal="telegram" if enviado_tg else "whatsapp"
                    )
                    session.add(notif)
                    
    session.commit()
    session.close()
    print(f"[{datetime.now()}] Chequeo finalizado.")

scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Programar a las 4:00 AM
    scheduler.add_job(check_updates, CronTrigger(hour=4, minute=0))
    scheduler.start()
    yield
    scheduler.shutdown()

load_dotenv()
init_db()

app = FastAPI(lifespan=lifespan, title="OpoRadar API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@app.get("/api/convocatorias")
def read_convocatorias(db: Session = Depends(get_db)):
    # Retornar convocatorias ordenadas por fecha descendente
    # Limitamos a 500 para no saturar
    return db.query(Convocatoria).order_by(Convocatoria.fecha_publicacion.desc()).limit(500).all()

@app.post("/api/trigger-sync")
def trigger_sync(background_tasks: BackgroundTasks):
    background_tasks.add_task(check_updates)
    return {"message": "Sincronización manual iniciada en segundo plano"}

@app.post("/api/generar-estudio/{convocatoria_id}")
def generar_estudio(convocatoria_id: str, db: Session = Depends(get_db)):
    conv = db.query(Convocatoria).filter_by(id=convocatoria_id).first()
    if not conv:
        return {"error": "Convocatoria no encontrada"}
        
    study = StudyGenerator()
    texto_base = f"{conv.titulo} {conv.observaciones} en {conv.entidad}"
    temario = study.generate_syllabus(texto_base)
    
    return {"temario": temario}

@app.post("/api/generar-test/{convocatoria_id}")
def generar_test(convocatoria_id: str, db: Session = Depends(get_db)):
    conv = db.query(Convocatoria).filter_by(id=convocatoria_id).first()
    if not conv:
        return {"error": "Convocatoria no encontrada"}
        
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
