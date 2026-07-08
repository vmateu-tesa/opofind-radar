"""Dossier de preparación heurístico para una convocatoria NUEVA.

Combina dos fuentes de información, ambas verificables y ninguna inventada:

1. `find_similar_processes`: procesos que OpoRadar ya tiene guardados en su
   propia base de datos (tabla `anuncios`) con una 'plaza' parecida a la del
   anuncio nuevo. Es una búsqueda heurística por similitud de texto (no usa
   FTS5 ni ningún índice: es una consulta SQL directa sobre `anuncios` más
   una comparación en Python), y solo puede encontrar lo que este sistema ya
   ha visto pasar desde que empezó a recopilar -- no es un histórico externo
   completo. Eso se deja explícito en la 'nota' de `build_dossier`.

2. `temario_references`: un diccionario ESTÁTICO y curado a mano de normativa
   general de función pública española (leyes reales del BOE), elegido por
   categoría detectada en el texto de la plaza mediante palabras clave. No hay
   LLM ni generación de texto libre: es una tabla fija de (título, URL). Cada
   URL se comprueba en caliente (HEAD, con GET de respaldo) antes de
   devolverla, y se descarta cualquiera que no responda 200 -- así un dossier
   nunca enlaza a una página caída aunque el BOE reorganice sus URLs con el
   tiempo. Los identificadores BOE-A-... concretos SÍ se verificaron a mano
   contra el título real de la ley antes de escribirlos aquí (ver tests y el
   historial de desarrollo): la comprobación en caliente es una red de
   seguridad frente a caídas puntuales o cambios de URL, no una verificación
   de que el contenido legal sea el correcto -- el buscador del BOE
   (`/buscar/act.php`) devuelve 200 incluso para un id inexistente (muestra
   una página de "no encontrado" con código 200), así que un 200 por sí solo
   no certifica que el id sea válido; lo que sí certifica es que la URL
   concreta aquí escrita fue comprobada manualmente contra el título oficial.

`build_dossier` junta ambas cosas en un dict lista para mostrar al usuario.
"""

import difflib
import re
import sqlite3

import requests

from app.scrapers.base import DEFAULT_HEADERS, DEFAULT_TIMEOUT
from app.utils import normalize_text

# Umbral de similitud (escala 0-1) por debajo del cual dos plazas NO se
# consideran "procesos similares". La métrica es la media de dos señales
# complementarias (ver `_similarity`):
#   - difflib.SequenceMatcher.ratio() sobre el texto normalizado completo:
#     captura similitud de cadena carácter a carácter (bueno para variantes
#     tipo "Auxiliar Administrativo" vs "Auxiliar Administrativo/a").
#   - solapamiento de tokens (índice de Jaccard) sobre las palabras del
#     texto normalizado: captura similitud aunque el orden de las palabras
#     cambie (p.ej. "Técnico de Sistemas de Información" vs "Técnico en
#     Sistemas de Información y Comunicaciones").
# 0.35 se eligió a mano probando con títulos de plaza reales de este
# proyecto: por debajo de eso empiezan a colarse pares sin relación real
# (p.ej. dos "Técnico" de especialidades distintas); por encima, se pierden
# variantes legítimas de la misma plaza con nombres bastante distintos.
SIMILARITY_THRESHOLD = 0.35


def _similarity(plaza_a: str, plaza_b: str) -> float:
    """Similitud heurística entre dos títulos de plaza, en [0, 1].
    Media de razón de secuencia (difflib) y solapamiento de tokens (Jaccard)
    sobre el texto normalizado (minúsculas, sin acentos) de ambos títulos."""
    norm_a = normalize_text(plaza_a)
    norm_b = normalize_text(plaza_b)
    if not norm_a or not norm_b:
        return 0.0

    ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()

    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    overlap = 0.0
    if tokens_a and tokens_b:
        overlap = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    return (ratio + overlap) / 2


def find_similar_processes(conn: sqlite3.Connection, anuncio: dict, limit: int = 5) -> list[dict]:
    """Busca en la tabla `anuncios` (consulta SQL directa, sin FTS5) otros
    procesos con 'plaza' parecida a la de `anuncio`, excluyendo el propio
    anuncio, ordenados por similitud descendente.

    `anuncio` es un dict con al menos 'plaza' (típicamente el registro que
    devuelve `app.db.upsert_anuncio`). Si trae 'id' (o 'fuente'+'external_id'),
    se usa para no devolver el propio anuncio como "similar a sí mismo".

    Devuelve como mucho `limit` elementos, cada uno con:
        {'plaza', 'entidad', 'fecha', 'url_bases', 'similitud'}
    donde 'fecha' es fecha_ini si existe, o fecha_fin en su defecto (ambas
    vienen tal cual de la BD, sin inventar ninguna), y 'similitud' está
    redondeada a 3 decimales. Solo se incluyen procesos con similitud >=
    SIMILARITY_THRESHOLD."""
    plaza = (anuncio.get("plaza") or "").strip()
    if not plaza:
        return []

    own_id = anuncio.get("id")
    own_fuente = anuncio.get("fuente")
    own_external_id = anuncio.get("external_id")

    rows = conn.execute(
        """SELECT id, fuente, external_id, plaza, entidad, fecha_ini, fecha_fin, url_bases
           FROM anuncios
           WHERE plaza IS NOT NULL AND TRIM(plaza) != ''"""
    ).fetchall()

    candidatos = []
    for row in rows:
        if own_id is not None and row["id"] == own_id:
            continue
        if own_id is None and own_fuente and own_external_id:
            if row["fuente"] == own_fuente and row["external_id"] == own_external_id:
                continue

        score = _similarity(plaza, row["plaza"])
        if score < SIMILARITY_THRESHOLD:
            continue

        candidatos.append({
            "plaza": row["plaza"],
            "entidad": row["entidad"] or "",
            "fecha": row["fecha_ini"] or row["fecha_fin"] or "",
            "url_bases": row["url_bases"] or "",
            "similitud": round(score, 3),
        })

    candidatos.sort(key=lambda c: c["similitud"], reverse=True)
    return candidatos[:limit]


# --- Referencias de temario: normativa general de función pública ----------
#
# Cada entrada es {'titulo': str, 'url': str}. Las URL apuntan siempre al
# texto consolidado del BOE (`/buscar/act.php?id=BOE-A-...`), verificado a
# mano (título real de la ley leído en la propia página) durante el
# desarrollo de este módulo. `temario_references` vuelve a comprobar cada URL
# en caliente antes de devolverla (ver `_url_ok`).

_EBEP = {
    "titulo": (
        "Real Decreto Legislativo 5/2015, de 30 de octubre, por el que se "
        "aprueba el texto refundido de la Ley del Estatuto Básico del "
        "Empleado Público (EBEP)"
    ),
    "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11719",
}

_LEY_39_2015 = {
    "titulo": (
        "Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo "
        "Común de las Administraciones Públicas (incluye el régimen de "
        "actuación administrativa automatizada y sede electrónica)"
    ),
    "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-10565",
}

_LEY_40_2015 = {
    "titulo": "Ley 40/2015, de 1 de octubre, de Régimen Jurídico del Sector Público",
    "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-10566",
}

_LEY_7_1985 = {
    "titulo": "Ley 7/1985, de 2 de abril, reguladora de las Bases del Régimen Local",
    "url": "https://www.boe.es/buscar/act.php?id=BOE-A-1985-5392",
}

_ENS = {
    "titulo": (
        "Real Decreto 311/2022, de 3 de mayo, por el que se regula el "
        "Esquema Nacional de Seguridad (ENS)"
    ),
    "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2022-7191",
}

_LOMLOE = {
    "titulo": (
        "Ley Orgánica 3/2020, de 29 de diciembre (LOMLOE), por la que se "
        "modifica la Ley Orgánica 2/2006, de 3 de mayo, de Educación"
    ),
    "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2020-17264",
}

# Normativa general común (EBEP + procedimiento administrativo + régimen
# jurídico + bases de régimen local): aplica a prácticamente cualquier
# proceso selectivo de función pública española, sea cual sea la categoría
# concreta detectada. Cada categoría parte de esta base y "añade" sus normas
# específicas encima (ver docstring del módulo y enunciado de la tarea).
_NORMATIVA_BASE = [_EBEP, _LEY_39_2015, _LEY_40_2015, _LEY_7_1985]

# Categoría -> (patrones de palabra clave sobre texto normalizado, normativa).
# Los patrones usan \b (word-boundary) para no disparar por substring dentro
# de otra palabra (mismo criterio que app/matcher.py).
_CATEGORIAS_NORMATIVA = {
    "administrativo": {
        "patrones": (r"\badministrativ\w*",),
        "referencias": _NORMATIVA_BASE,
    },
    "informatico_sistemas": {
        "patrones": (r"\binformatic\w*", r"\bsistemas?\b", r"\btic\b"),
        "referencias": _NORMATIVA_BASE + [_ENS],
    },
    "docente": {
        "patrones": (r"\bdocente\w*", r"\bprofesor\w*", r"\bmaestr[oa]\w*"),
        "referencias": _NORMATIVA_BASE + [_LOMLOE],
    },
}


def _url_ok(url: str, timeout: int = DEFAULT_TIMEOUT) -> bool:
    """Comprueba en caliente que `url` responde 200 antes de incluirla en un
    dossier. Intenta HEAD primero (más barato); si el servidor no lo soporta
    bien (código != 200) cae a GET. Cualquier error de red se trata como "no
    disponible" (False), nunca como excepción que rompa el dossier."""
    try:
        resp = requests.head(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200:
            return True
        resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True, stream=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def temario_references(plaza: str) -> list[dict]:
    """Referencias de normativa general de función pública aplicables a
    `plaza`, según la(s) categoría(s) detectada(s) por palabras clave sobre
    el texto normalizado. Si no se detecta ninguna categoría conocida,
    devuelve una lista vacía (no se inventa normativa para categorías sin
    curar).

    Cada URL se comprueba en caliente (`_url_ok`) antes de devolverse; las
    que no respondan 200 se descartan silenciosamente. En tests, monkeypatch
    `app.dossier._url_ok` para no depender de red real."""
    texto = normalize_text(plaza or "")
    if not texto:
        return []

    referencias: list[dict] = []
    urls_vistas: set[str] = set()
    for categoria in _CATEGORIAS_NORMATIVA.values():
        detectada = any(re.search(patron, texto) for patron in categoria["patrones"])
        if not detectada:
            continue
        for ref in categoria["referencias"]:
            if ref["url"] in urls_vistas:
                continue
            urls_vistas.add(ref["url"])
            referencias.append(ref)

    return [ref for ref in referencias if _url_ok(ref["url"])]


def build_dossier(conn: sqlite3.Connection, anuncio: dict) -> dict:
    """Dossier de preparación heurístico para `anuncio` (una convocatoria
    NUEVA): procesos similares ya vistos por OpoRadar + referencias de
    temario genérico aplicables por categoría. Todo el contenido sale de la
    propia BD o de la tabla estática de normativa verificada; no hay LLM ni
    texto generado libremente."""
    return {
        "procesos_similares": find_similar_processes(conn, anuncio),
        "temario_referencias": temario_references(anuncio.get("plaza", "")),
        "nota": (
            "Los 'procesos similares' son únicamente convocatorias que OpoRadar ya "
            "ha detectado y guardado en su propia base de datos desde que empezó a "
            "recopilar: no es un histórico completo ni oficial de todo lo publicado "
            "alguna vez por estas administraciones, solo lo que este sistema ha visto "
            "pasar hasta ahora. Las 'referencias de temario' son normativa general de "
            "función pública española (leyes reales del BOE) elegida por categoría "
            "detectada en el nombre de la plaza; es un punto de partida genérico, no "
            "un temario oficial específico de esta convocatoria -- las bases oficiales "
            "de la propia convocatoria son siempre la fuente que manda."
        ),
    }


if __name__ == "__main__":
    import sys

    from app.db import get_connection

    conn = get_connection(sys.argv[1] if len(sys.argv) > 1 else "data/oporadar.db")
    ejemplo = {"plaza": "Técnico Informático de Sistemas", "entidad": "Diputación de Alicante"}
    import json

    print(json.dumps(build_dossier(conn, ejemplo), ensure_ascii=False, indent=2))
