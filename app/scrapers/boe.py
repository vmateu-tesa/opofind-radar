"""Scraper del Boletín Oficial del Estado (BOE): sección II-B, "Oposiciones y
concursos", vía la API de datos abiertos del BOE.

La sección "II. Autoridades y personal" del BOE se publica dividida en dos
subsecciones con código propio (no existe un código "II" plano):

    2A -- "A. Nombramientos, situaciones e incidencias" (movimientos
           individuales de funcionarios: nombramientos a puesto concreto,
           ceses, destinos, escalafones...). NO son procesos selectivos
           públicos y se ignoran aquí.
    2B -- "B. Oposiciones y concursos". Es la subsección de interés para
           OpoRadar: convocatorias de plaza/proceso selectivo y sus trámites
           posteriores (tribunales, listas de admitidos, correcciones...).

Solo se recorre 2B. El matcher de perfiles (app/matcher.py) se encarga de
filtrar por contenido después; aquí no se descarta nada dentro de 2B (ni
siquiera los trámites que no son "convocatoria nueva") para no perder
avisos relevantes como ampliaciones de plazo.
"""

import datetime as dt
import logging

import requests

from app.models import AnuncioRaw
from app.scrapers.base import DEFAULT_HEADERS, DEFAULT_TIMEOUT, RateLimiter

logger = logging.getLogger(__name__)

FUENTE = "boe"

SUMARIO_URL_TMPL = "https://www.boe.es/datosabiertos/api/boe/sumario/{fecha}"

# Código de la subsección "II.B Oposiciones y concursos" dentro del sumario diario.
SECCION_OPOSICIONES = "2B"

# Rate limiter propio para boe.es (independiente del de sede.diputacionalicante.es).
boe_rate_limiter = RateLimiter(min_interval_seconds=1.0)


def _as_list(value):
    """Normaliza un nodo del sumario del BOE a lista siempre.

    El JSON del BOE viene de convertir XML: cuando un nodo tiene un único
    hijo, la librería de conversión lo entrega como dict suelto en vez de
    como lista de un elemento. Hay que defender esto en los 4 niveles
    (diario, seccion, departamento/epigrafe, epigrafe/item) o el parser
    revienta el día que solo haya un elemento."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _fetch_sumario(fecha: str) -> dict | None:
    """Descarga el sumario diario del BOE (fecha en formato YYYYMMDD).

    Devuelve None si ese día no hubo boletín (404: fines de semana y
    festivos), lo cual es el comportamiento normal de la API, no un error."""
    url = SUMARIO_URL_TMPL.format(fecha=fecha)
    headers = dict(DEFAULT_HEADERS)
    headers["Accept"] = "application/json"

    boe_rate_limiter.wait()
    resp = requests.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def _parse_item(item: dict, entidad: str, epigrafe_nombre: str) -> AnuncioRaw | None:
    """Convierte un "item" (disposición individual) del sumario en AnuncioRaw."""
    identificador = (item.get("identificador") or "").strip()
    titulo = (item.get("titulo") or "").strip()
    if not identificador or not titulo:
        logger.warning("boe: item sin identificador o título, se descarta: %s", item)
        return None

    url_pdf = item.get("url_pdf") or {}
    url_bases = (url_pdf.get("texto") or item.get("url_html") or "").strip()

    raw_data = dict(item)
    if epigrafe_nombre:
        raw_data["_epigrafe"] = epigrafe_nombre

    return AnuncioRaw(
        fuente=FUENTE,
        external_id=identificador,
        plaza=titulo,
        entidad=entidad or "",
        vacantes="",
        url_bases=url_bases,
        fecha_ini="",
        fecha_fin="",
        obs="",
        raw_data=raw_data,
    )


def _procesar_seccion_oposiciones(seccion: dict) -> list[AnuncioRaw]:
    """Recorre departamento -> epigrafe -> item de la sección 2B ya localizada."""
    anuncios: list[AnuncioRaw] = []

    for departamento in _as_list(seccion.get("departamento")):
        entidad = (departamento.get("nombre") or "").strip()
        epigrafes = _as_list(departamento.get("epigrafe"))

        if epigrafes:
            for epigrafe in epigrafes:
                epigrafe_nombre = (epigrafe.get("nombre") or "").strip()
                for item in _as_list(epigrafe.get("item")):
                    anuncio = _parse_item(item, entidad, epigrafe_nombre)
                    if anuncio:
                        anuncios.append(anuncio)
        else:
            # Caso defensivo: departamento con "item" directo, sin epígrafe
            # intermedio (no observado en la muestra real, pero es la forma
            # habitual de este tipo de endpoints y conviene no romper si aparece).
            for item in _as_list(departamento.get("item")):
                anuncio = _parse_item(item, entidad, "")
                if anuncio:
                    anuncios.append(anuncio)

    return anuncios


def _procesar_sumario(data: dict) -> list[AnuncioRaw]:
    """Extrae los anuncios de la sección 2B de un sumario diario ya descargado."""
    anuncios: list[AnuncioRaw] = []
    sumario = ((data or {}).get("data") or {}).get("sumario") or {}

    for diario in _as_list(sumario.get("diario")):
        for seccion in _as_list(diario.get("seccion")):
            if seccion.get("codigo") != SECCION_OPOSICIONES:
                continue
            anuncios.extend(_procesar_seccion_oposiciones(seccion))

    return anuncios


def fetch(dias_atras: int = 7) -> list[AnuncioRaw]:
    """Recorre los sumarios del BOE de los últimos `dias_atras` días (incluido
    hoy) y devuelve los AnuncioRaw de la sección II.B "Oposiciones y
    concursos" de todos ellos.

    Los días sin boletín (404: fines de semana, festivos) se saltan sin
    tratarse como error. Los errores de red puntuales en un día concreto se
    loguean y se continúa con el resto de días."""
    anuncios: list[AnuncioRaw] = []
    hoy = dt.date.today()
    dias_con_boletin = 0

    for delta in range(dias_atras):
        fecha = hoy - dt.timedelta(days=delta)
        fecha_str = fecha.strftime("%Y%m%d")

        try:
            data = _fetch_sumario(fecha_str)
        except requests.RequestException:
            logger.exception("boe: error de red al pedir el sumario del %s", fecha_str)
            continue

        if data is None:
            logger.debug("boe: sin boletín el %s (404, normal en fin de semana/festivo)", fecha_str)
            continue

        dias_con_boletin += 1
        anuncios.extend(_procesar_sumario(data))

    logger.info(
        "boe: %d anuncio(s) de la sección II.B en %d día(s) con boletín (de %d días revisados)",
        len(anuncios), dias_con_boletin, dias_atras,
    )
    return anuncios


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    items = fetch()
    print(f"Total anuncios BOE sección II.B: {len(items)}")
    for a in items[:5]:
        print(f"- [{a.external_id}] {a.entidad}: {a.plaza[:90]}")
