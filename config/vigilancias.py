"""Vigilancias dirigidas: plazas MUY concretas que el usuario quiere seguir
de forma fija, aunque todavia no se hayan convocado.

A diferencia del seguimiento normal (que se marca sobre una convocatoria ya
existente) o de los municipios favoritos (que avisan de cualquier oferta de
un municipio), una vigilancia describe una plaza objetivo por sus palabras
clave y se comprueba en CADA ejecucion del cron: en cuanto aparece una
convocatoria que encaja, se dispara un aviso PRIORITARIO ("la plaza que
vigilas ha salido") por todos los canales, para enterarse el primero.

Las vigilancias se declaran aqui (fijas, versionadas con el codigo) y se
sincronizan a la tabla `vigilancias` al arrancar. La tabla guarda el ESTADO
(vigilando / detectada); esta lista guarda las REGLAS de deteccion.

Caso que la motiva: el usuario perdio la bolsa de Ingeniero/a de
Telecomunicaciones de Elche por no enterarse a tiempo. Benidorm ha
transformado en su RPT (modificacion nº 4, BOP 30/10/2025) el puesto
1.11.139 de "Ingeniero Tecnico Topografia" a "Ingeniero Tecnico
Telecomunicacion"; cuando se convoque el proceso para cubrirlo, quiere el
aviso inmediato.
"""

import unicodedata


def _norm(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto).lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Cada vigilancia:
#   slug            id estable (no cambiar una vez desplegada)
#   titulo/entidad/municipio/enlace/notas  metadatos mostrados en la app
#   municipios      si se indica, la convocatoria debe ser de alguno de ellos
#                   (por municipio detectado o por nombre en la entidad)
#   incluye_todas   TODAS estas cadenas deben aparecer en el texto
#   incluye_alguna  al menos UNA de estas debe aparecer (si la lista no vacia)
VIGILANCIAS = [
    {
        "slug": "benidorm-ing-tecnico-telecomunicacion",
        "titulo": "Ingeniero/a Técnico/a de Telecomunicación — Benidorm",
        "entidad": "Ayuntamiento de Benidorm",
        "municipio": "Benidorm",
        "enlace": "https://contenidos.benidorm.org/sites/default/files/descargas/2025-10/anuncio%20bop%2030_10_2025%20%28modificaci%C3%B3n%20n%C2%BA%204%29.pdf",
        "notas": "Transformación del puesto 1.11.139 en la RPT (BOP 30/10/2025, "
                 "modificación nº 4): de Ingeniero Técnico de Topografía a Ingeniero "
                 "Técnico de Telecomunicación. Avisar en cuanto se convoque el proceso "
                 "o bolsa para cubrir la plaza.",
        "municipios": ["Benidorm"],
        "incluye_todas": [],
        # Telecomunicación en Benidorm, o el propio código de puesto de la RPT.
        "incluye_alguna": ["telecomunicac", "1.11.139"],
    },
]


def coincide(vig: dict, titulo: str = "", entidad: str = "", observaciones: str = "",
             municipio: str = "") -> bool:
    """True si una convocatoria encaja con la vigilancia ``vig``.

    Combina un texto normalizado (titulo + entidad + observaciones) con el
    municipio detectado. Criterio: restriccion opcional por municipio +
    todas las cadenas de ``incluye_todas`` + al menos una de
    ``incluye_alguna``. Pensado para alto recall (mejor un aviso de mas que
    perder la plaza)."""
    texto = _norm(f"{titulo} {entidad} {observaciones}")

    munis = vig.get("municipios") or []
    if munis:
        munis_norm = {_norm(m) for m in munis}
        ent_norm = _norm(entidad)
        muni_norm = _norm(municipio)
        if muni_norm not in munis_norm and not any(m in ent_norm for m in munis_norm):
            return False

    for clave in vig.get("incluye_todas") or []:
        if _norm(clave) not in texto:
            return False

    algunas = vig.get("incluye_alguna") or []
    if algunas and not any(_norm(clave) in texto for clave in algunas):
        return False

    return True


def por_slug(slug: str):
    for vig in VIGILANCIAS:
        if vig["slug"] == slug:
            return vig
    return None
