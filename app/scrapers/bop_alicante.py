"""Scraper del Boletín Oficial de la Provincia de Alicante (BOP), sección
"III. Administración Local", vía el endpoint AJAX interno que usa el
buscador de la sede electrónica de la Diputación de Alicante.

Origen del endpoint
--------------------
La página https://sede.diputacionalicante.es/consultas-bop/ tiene un
`<form>` visible con un campo de fecha y un `<select>` de tipo de organismo,
pero ese formulario es decorativo (sin botón submit, nunca se envía como tal).
Un `<script>` inline de esa misma página dispara, en su lugar, una llamada
AJAX (jQuery $.getJSON) a:

    GET https://sede.diputacionalicante.es/wp-content/themes/Desarrollo-Diputacion/webservices/wseConsultaAjax.php
    Params: nemo=BOP_CON ; usuario=- ; param=<raiz><entrada><registro>
            <fechaPub>DD/MM/YYYY</fechaPub><tipoorganismo>4</tipoorganismo>
            </registro></entrada></raiz>   (XML crudo, va url-encoded)

Es una consulta POR DÍA CONCRETO ya filtrada server-side por tipoorganismo:
no hay listado de "últimos N anuncios" ni rango de fechas en una sola
llamada. tipoorganismo=4 es "III. Administración Local" (ayuntamientos,
mancomunidades...), la categoría de interés aquí.

No hace falta cookie de sesión, CSRF token, Referer ni X-Requested-With
(probado explícitamente en sesión nueva): no hay captcha en este endpoint.
Si un día no hubo boletín (fin de semana / festivo) la respuesta es HTTP 200
con `{"error": "..."}` en vez de la clave "boletin"; es el comportamiento
normal, no un fallo.

Por qué es una fuente SECUNDARIA
---------------------------------
El campo `extracto` de cada registro mezcla CUALQUIER tipo de anuncio
municipal (urbanismo, contratación, ordenanzas, notificaciones...), no solo
empleo público. Por eso aquí se aplica un filtro amplio de palabras clave de
empleo público (`EMPLEO_PUBLICO_RE`) sobre el extracto antes de dar de alta
un `AnuncioRaw` -- si no, se metería en la base de datos un aluvión de
anuncios irrelevantes que ningún perfil de app/matcher.py llegaría a
notificar de todos modos. Este filtro es deliberadamente amplio y genérico
("¿esto es empleo público?"); no sustituye al matcher fino por perfil, que
se aplica después, centralizado, sobre lo que ya se ha dado de alta.

Además, el diseño del proyecto ya usa la tabla de "otras oposiciones" para
anotar en su campo Obs cuándo el BOP publica algo de cada proceso ya
conocido por la fuente principal. Este scraper sirve sobre todo para
detectar avisos de empleo público que aún NO estén reflejados por esa fuente
principal, o para aportar el enlace directo al PDF del BOP.

Sobre el external_id
---------------------
El nombre de fichero del PDF en `ubicacion` tiene forma "AAAA_NNNNNN.pdf"
(guion bajo entre año y edicto), por lo que `app/utils.py:extract_pdf_id()`
(regex `r"/(\\d+)\\.pdf"`) NO lo captura -- el guion bajo rompe la coincidencia
de dígitos justo tras la última barra, así que siempre devuelve None con
estas URLs. En su lugar se construye el id directamente como
f"{anyo}-{edicto}" (p.ej. "2026-5200"), que ya es único y estable por sí
mismo dentro de la Diputación (no hace falta stable_fallback_id).
"""

import datetime as dt
import logging
import re

import requests

from app.models import AnuncioRaw
from app.scrapers.base import DEFAULT_HEADERS, DEFAULT_TIMEOUT, diputacion_rate_limiter
from app.utils import normalize_text

logger = logging.getLogger(__name__)

FUENTE = "bop_alicante"

CONSULTA_URL = (
    "https://sede.diputacionalicante.es/wp-content/themes/"
    "Desarrollo-Diputacion/webservices/wseConsultaAjax.php"
)

# Value del <select name="tipoorganismo"> para "III. ADMINISTRACIÓN LOCAL"
# (ayuntamientos, mancomunidades, organismos autónomos locales...).
TIPOORGANISMO_ADMIN_LOCAL = "4"

PARAM_TMPL = (
    "<raiz><entrada><registro>"
    "<fechaPub>{fecha_ddmmyyyy}</fechaPub>"
    "<tipoorganismo>{tipoorganismo}</tipoorganismo>"
    "</registro></entrada></raiz>"
)

# Filtro amplio de "¿esto suena a empleo público?" sobre app.utils.normalize_text
# (minúsculas, sin acentos). Deliberadamente generoso: es preferible colar
# algún falso positivo que perder una convocatoria real por un patrón
# demasiado estricto.
EMPLEO_PUBLICO_RE = re.compile(
    r"oferta.{0,15}empleo|"
    r"oposicion|"
    r"concurso.{0,15}oposicion|"
    r"proceso selectivo|"
    r"procesos selectivos|"
    r"convocatoria|"
    r"bolsa.{0,10}(trabajo|empleo)|"
    r"\bfuncionari|"
    r"personal laboral|"
    r"plaza.{0,15}vacante|"
    r"provision.{0,10}plaza|"
    r"lista.{0,15}(provisional|definitiv).{0,15}admitid|"
    r"tribunal.{0,10}calificador|"
    r"bases.{0,20}(especific|general).{0,20}(convocatoria|selectiv|plaza)"
)


def _es_empleo_publico(extracto: str) -> bool:
    return bool(EMPLEO_PUBLICO_RE.search(normalize_text(extracto or "")))


def _first(value, default: str = "") -> str:
    """Los campos del JSON vienen siempre como listas de 1 elemento (típico
    de una conversión XML->JSON). Indexa [0] a prueba de listas vacías/None."""
    if not value:
        return default
    if isinstance(value, list):
        return value[0] if value else default
    return value


def _fetch_dia(fecha: dt.date, tipoorganismo: str = TIPOORGANISMO_ADMIN_LOCAL) -> dict | None:
    """Descarga el boletín publicado en `fecha` (ya filtrado server-side por
    tipoorganismo). Devuelve None si ese día no hubo boletín (fin de semana,
    festivo): la respuesta normal en ese caso es HTTP 200 con
    {"error": "..."} en vez de la clave "boletin"."""
    param = PARAM_TMPL.format(
        fecha_ddmmyyyy=fecha.strftime("%d/%m/%Y"), tipoorganismo=tipoorganismo
    )
    params = {"nemo": "BOP_CON", "usuario": "-", "param": param}

    diputacion_rate_limiter.wait()
    resp = requests.get(CONSULTA_URL, params=params, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if not isinstance(data, dict) or "boletin" not in data:
        return None
    return data


def _parse_registro(registro: dict) -> AnuncioRaw | None:
    """Convierte un "registro" (anuncio individual) en AnuncioRaw, o None si
    no parece empleo público o le faltan campos imprescindibles."""
    extracto = _first(registro.get("extracto")).strip()
    if not extracto or not _es_empleo_publico(extracto):
        return None

    anyo = _first(registro.get("anyo")).strip()
    edicto = _first(registro.get("edicto")).strip()
    if not anyo or not edicto:
        logger.warning("bop_alicante: registro de empleo público sin anyo/edicto, se descarta: %s", registro)
        return None

    entidad = _first(registro.get("denominacion")).strip() or _first(registro.get("ampliacion")).strip()
    n_bop = _first(registro.get("nBop")).strip()
    desecun = _first(registro.get("desecun")).strip()
    obs_parts = []
    if n_bop:
        obs_parts.append(f"BOP nº{n_bop}/{anyo}")
    if desecun:
        obs_parts.append(f"({desecun})")

    return AnuncioRaw(
        fuente=FUENTE,
        external_id=f"{anyo}-{edicto}",
        plaza=extracto,
        entidad=entidad,
        vacantes="",
        url_bases=_first(registro.get("ubicacion")).strip(),
        fecha_ini=_first(registro.get("fechaPublica")).strip(),
        fecha_fin="",
        obs=" ".join(obs_parts),
        raw_data=dict(registro),
    )


def _procesar_dia(data: dict) -> list[AnuncioRaw]:
    """Recorre boletin.bop[*].registro[*] de un día ya descargado."""
    anuncios: list[AnuncioRaw] = []
    bop_list = (data.get("boletin") or {}).get("bop") or []
    for bop in bop_list:
        for registro in bop.get("registro") or []:
            anuncio = _parse_registro(registro)
            if anuncio:
                anuncios.append(anuncio)
    return anuncios


def fetch(dias_atras: int = 2) -> list[AnuncioRaw]:
    """Recorre los últimos `dias_atras` días (incluido hoy) de la categoría
    "III. Administración Local" del BOP de Alicante y devuelve los anuncios
    cuyo extracto suena a empleo público (ver EMPLEO_PUBLICO_RE).

    El valor por defecto es deliberadamente pequeño (hoy + ayer, por si el
    cron corrió tarde): no existe forma de pedir un rango de fechas en una
    sola llamada a este endpoint, así que un `dias_atras` grande implica esa
    cantidad de peticiones secuenciales (respetando diputacion_rate_limiter).
    Úsese un valor mayor solo para un backfill puntual inicial.

    Los días sin boletín (fin de semana, festivos) se saltan sin tratarse
    como error. Los errores de red o de parseo en un día concreto se loguean
    y se continúa con el resto de días."""
    anuncios: list[AnuncioRaw] = []
    hoy = dt.date.today()
    dias_con_boletin = 0

    for delta in range(dias_atras):
        fecha = hoy - dt.timedelta(days=delta)

        try:
            data = _fetch_dia(fecha)
        except requests.RequestException:
            logger.exception("bop_alicante: error de red al pedir el boletín del %s", fecha.isoformat())
            continue
        except ValueError:
            logger.exception("bop_alicante: respuesta no-JSON del %s", fecha.isoformat())
            continue

        if data is None:
            logger.debug("bop_alicante: sin boletín el %s (normal en fin de semana/festivo)", fecha.isoformat())
            continue

        dias_con_boletin += 1
        anuncios.extend(_procesar_dia(data))

    logger.info(
        "bop_alicante: %d anuncio(s) de empleo público en %d día(s) con boletín (de %d días revisados)",
        len(anuncios), dias_con_boletin, dias_atras,
    )
    return anuncios


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    items = fetch()
    print(f"Total anuncios bop_alicante (empleo público, admin. local): {len(items)}")
    for a in items[:10]:
        print(f"- [{a.external_id}] {a.entidad}: {a.plaza[:90]}")
