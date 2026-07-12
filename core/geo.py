"""Filtro geografico: ¿este anuncio es de la provincia de Alicante?

El BOE (nacional) y el DOGV (toda la Comunidad Valenciana: Valencia,
Castellon y Alicante) traen convocatorias de fuera de nuestro ambito. Este
modulo decide si un anuncio pertenece a la provincia de Alicante para
descartar el ruido de otras provincias.

Filosofia: es un filtro para REDUCIR RUIDO en fuentes supra-provinciales,
no la garantia de cobertura. La cobertura completa de la provincia la da el
BOP de Alicante (que por definicion ya es solo de Alicante). Por eso el
criterio es deliberadamente generoso: ante la duda, mejor incluir. Si un
municipio pequeño no estuviera en la lista, el BOP lo cubre igual.

El match es sobre texto normalizado (minusculas, sin acentos) de la entidad
y, en segunda instancia, del titulo (a veces el nombre del ayuntamiento va
en el titulo y no en la entidad, p.ej. en el BOE).
"""

import re
import unicodedata


def _norm(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Municipios de la provincia de Alicante (las 141 localidades, en sus formas
# en castellano y en valenciano cuando difieren). Normalizados sin acentos.
# Se listan por comarcas para poder mantenerlo. No pretende ser una lista
# oficial cerrada: sirve para el filtro de ruido descrito arriba.
_MUNICIPIOS_RAW = [
    # Marina Baixa
    "alfas del pi", "l'alfas del pi", "alfaz del pi", "altea", "beniarda",
    "benifato", "benimantell", "benidorm", "bolulla", "callosa d'en sarria",
    "callosa de ensarria", "confrides", "finestrat", "guadalest",
    "el castell de guadalest", "la nucia", "nucia", "orxeta", "polop",
    "relleu", "sella", "tarbena", "la vila joiosa", "villajoyosa",
    # Marina Alta
    "adsubia", "l'atzubia", "alcalali", "beniarbeig", "benidoleig",
    "benigembla", "benimeli", "benissa", "benitachell", "el poble nou de benitatxell",
    "calpe", "calp", "castell de castells", "denia", "gata de gorgos",
    "xabia", "javea", "xalo", "jalon", "lliber", "murla", "ondara",
    "orba", "parcent", "pedreguer", "pego", "els poblets", "rafol d'almunia",
    "sagra", "sanet y negrals", "senija", "teulada", "tormos", "vall d'alcala",
    "la vall d'alcala", "vall d'ebo", "la vall d'ebo", "vall de gallinera",
    "la vall de gallinera", "vall de laguar", "la vall de laguar", "verger", "el verger",
    # l'Alacanti
    "aigues", "alicante", "alacant", "busot", "el campello", "campello",
    "sant joan d'alacant", "san juan de alicante", "mutxamel", "muchamiel",
    "sant vicent del raspeig", "san vicente del raspeig", "la torre de les macanes",
    "torremanzanas", "xixona", "jijona", "agost",
    # Baix Vinalopo
    "crevillent", "crevillente", "elx", "elche", "santa pola",
    # Vinalopo Mitja
    "asp", "aspe", "algueña", "algueny", "el fondo de les neus", "hondon de las nieves",
    "hondon de los frailes", "la romana", "monforte del cid", "monover", "monovar",
    "novelda", "el pinos", "pinoso", "elda", "petrer", "salinas",
    # Alt Vinalopo
    "banyeres de mariola", "beneixama", "biar", "camp de mirra", "el camp de mirra",
    "la canada", "sax", "villena",
    # l'Alcoia
    "alcoi", "alcoy", "baneres", "benifallim", "castalla", "cocentaina",
    "ibi", "onil", "penaguila", "la torre de les macanes", "tibi",
    # El Comtat
    "agres", "alcocer de planes", "alcoleja", "almudaina", "alqueria d'asnar",
    "l'alqueria d'asnar", "balones", "benasau", "beniarres", "benilloba",
    "benillup", "benimarfull", "benimassot", "cocentaina", "facheca", "fageca",
    "famorca", "gaianes", "gorga", "l'orxa", "lorcha", "millena", "muro de alcoy",
    "muro d'alcoi", "planes", "quatretondeta", "tollos",
    # Baix Segura / Vega Baja
    "albatera", "algorfa", "almoradi", "benejuzar", "benferri", "benijofar",
    "bigastro", "callosa de segura", "catral", "cox", "daya nueva", "daya vieja",
    "dolores", "formentera del segura", "granja de rocamora", "guardamar del segura",
    "jacarilla", "los montesinos", "orihuela", "el pilar de la horadada",
    "pilar de la horadada", "rafal", "redovan", "rojales", "san fulgencio",
    "san isidro", "san miguel de salinas", "torrevieja", "los montesinos",
]

_MUNICIPIOS = frozenset(_norm(m) for m in _MUNICIPIOS_RAW)

# Marcadores directos de provincia (cuando el texto lo dice explicitamente).
_MARCADORES = tuple(_norm(m) for m in (
    "alicante", "alacant", "provincia de alicante", "provincia d'alacant",
))

# Diputacion de Alicante y sus organismos son de la provincia por definicion.
_MARCADORES_ENTIDAD = tuple(_norm(m) for m in (
    "diputacion de alicante", "diputacion provincial de alicante",
    "excma. diputacion provincial de alicante", "suma gestion tributaria",
))


def _contiene_municipio(texto_norm: str) -> bool:
    # Match por palabra/segmento: buscamos el nombre del municipio como
    # subcadena delimitada para no confundir 'agost' dentro de otra palabra.
    for muni in _MUNICIPIOS:
        # los nombres compuestos (con espacios) se buscan como subcadena directa
        if " " in muni or "'" in muni:
            if muni in texto_norm:
                return True
        else:
            # nombre simple: exige limites de palabra
            if re.search(r"\b" + re.escape(muni) + r"\b", texto_norm):
                return True
    return False


def es_alicante(entidad: str = "", titulo: str = "") -> bool:
    """True si el anuncio parece pertenecer a la provincia de Alicante.

    Mira primero la entidad (donde suele ir el nombre del ayuntamiento) y,
    si no encuentra nada, el titulo. Criterio generoso: cualquier municipio
    de la provincia, marcador de provincia, o la Diputacion de Alicante."""
    ent = _norm(entidad)
    tit = _norm(titulo)

    for marcador in _MARCADORES_ENTIDAD:
        if marcador in ent:
            return True

    combinado = ent + " || " + tit
    for marcador in _MARCADORES:
        if marcador in combinado:
            return True

    if _contiene_municipio(ent):
        return True
    if _contiene_municipio(tit):
        return True
    return False
