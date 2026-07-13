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

Ademas del filtro binario ``es_alicante``, este modulo asigna a cada anuncio
su municipio CANONICO (``municipio_de``), que es la base de la funcionalidad
de "municipios favoritos": el usuario marca municipios y recibe aviso de
cualquier oferta nueva/actualizada de ellos.
"""

import re
import unicodedata


def _norm(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Municipios de la provincia de Alicante, por comarcas: nombre CANONICO (el
# que se muestra en la interfaz y se guarda como favorito) -> variantes con
# las que puede aparecer en las fuentes (castellano/valenciano, con o sin
# articulo, erratas frecuentes). Las variantes se normalizan al construir
# las estructuras de busqueda, asi que pueden escribirse con acentos.
# No pretende ser una lista oficial cerrada: sirve para el filtro de ruido
# descrito arriba y para el selector de favoritos.
MUNICIPIOS_CANONICOS = {
    # Marina Baixa
    "L'Alfàs del Pi": ("alfas del pi", "l'alfas del pi", "alfaz del pi"),
    "Altea": ("altea",),
    "Beniardà": ("beniarda",),
    "Benifato": ("benifato",),
    "Benimantell": ("benimantell",),
    "Benidorm": ("benidorm",),
    "Bolulla": ("bolulla",),
    "Callosa d'en Sarrià": ("callosa d'en sarria", "callosa de ensarria"),
    "Confrides": ("confrides",),
    "Finestrat": ("finestrat",),
    "El Castell de Guadalest": ("guadalest", "el castell de guadalest"),
    "La Nucía": ("la nucia", "nucia"),
    "Orxeta": ("orxeta",),
    "Polop": ("polop",),
    "Relleu": ("relleu",),
    "Sella": ("sella",),
    "Tàrbena": ("tarbena",),
    "Villajoyosa": ("la vila joiosa", "villajoyosa"),
    # Marina Alta
    "L'Atzúbia": ("adsubia", "l'atzubia"),
    "Alcalalí": ("alcalali",),
    "Beniarbeig": ("beniarbeig",),
    "Benidoleig": ("benidoleig",),
    "Benigembla": ("benigembla",),
    "Benimeli": ("benimeli",),
    "Benissa": ("benissa",),
    "Benitatxell": ("benitachell", "el poble nou de benitatxell"),
    "Calpe": ("calpe", "calp"),
    "Castell de Castells": ("castell de castells",),
    "Dénia": ("denia",),
    "Gata de Gorgos": ("gata de gorgos",),
    "Jávea": ("xabia", "javea"),
    "Jalón": ("xalo", "jalon"),
    "Llíber": ("lliber",),
    "Murla": ("murla",),
    "Ondara": ("ondara",),
    "Orba": ("orba",),
    "Parcent": ("parcent",),
    "Pedreguer": ("pedreguer",),
    "Pego": ("pego",),
    "Els Poblets": ("els poblets",),
    "El Ràfol d'Almúnia": ("rafol d'almunia",),
    "Sagra": ("sagra",),
    "Sanet y Negrals": ("sanet y negrals",),
    "Senija": ("senija",),
    "Teulada": ("teulada",),
    "Tormos": ("tormos",),
    "La Vall d'Alcalà": ("vall d'alcala", "la vall d'alcala"),
    "La Vall d'Ebo": ("vall d'ebo", "la vall d'ebo"),
    "La Vall de Gallinera": ("vall de gallinera", "la vall de gallinera"),
    "La Vall de Laguar": ("vall de laguar", "la vall de laguar"),
    "El Verger": ("verger", "el verger"),
    # l'Alacanti
    "Aigües": ("aigues",),
    "Alicante": ("alicante", "alacant"),
    "Busot": ("busot",),
    "El Campello": ("el campello", "campello"),
    "Sant Joan d'Alacant": ("sant joan d'alacant", "san juan de alicante"),
    "Mutxamel": ("mutxamel", "muchamiel"),
    "San Vicente del Raspeig": ("sant vicent del raspeig", "san vicente del raspeig"),
    "La Torre de les Maçanes": ("la torre de les macanes", "torremanzanas"),
    "Jijona": ("xixona", "jijona"),
    "Agost": ("agost",),
    # Baix Vinalopo
    "Crevillente": ("crevillent", "crevillente"),
    "Elche": ("elx", "elche"),
    "Santa Pola": ("santa pola",),
    # Vinalopo Mitja
    "Aspe": ("asp", "aspe"),
    "Algueña": ("algueña", "algueny"),
    "Hondón de las Nieves": ("el fondo de les neus", "hondon de las nieves"),
    "Hondón de los Frailes": ("hondon de los frailes",),
    "La Romana": ("la romana",),
    "Monforte del Cid": ("monforte del cid",),
    "Monóvar": ("monover", "monovar"),
    "Novelda": ("novelda",),
    "Pinoso": ("el pinos", "pinoso"),
    "Elda": ("elda",),
    "Petrer": ("petrer",),
    "Salinas": ("salinas",),
    # Alt Vinalopo
    "Banyeres de Mariola": ("banyeres de mariola", "baneres"),
    "Beneixama": ("beneixama",),
    "Biar": ("biar",),
    "El Camp de Mirra": ("camp de mirra", "el camp de mirra"),
    "Cañada": ("la canada",),
    "Sax": ("sax",),
    "Villena": ("villena",),
    # l'Alcoia
    "Alcoy": ("alcoi", "alcoy"),
    "Benifallim": ("benifallim",),
    "Castalla": ("castalla",),
    "Ibi": ("ibi",),
    "Onil": ("onil",),
    "Penàguila": ("penaguila",),
    "Tibi": ("tibi",),
    # El Comtat
    "Agres": ("agres",),
    "Alcocer de Planes": ("alcocer de planes",),
    "Alcoleja": ("alcoleja",),
    "Almudaina": ("almudaina",),
    "L'Alqueria d'Asnar": ("alqueria d'asnar", "l'alqueria d'asnar"),
    "Balones": ("balones",),
    "Benasau": ("benasau",),
    "Beniarrés": ("beniarres",),
    "Benilloba": ("benilloba",),
    "Benillup": ("benillup",),
    "Benimarfull": ("benimarfull",),
    "Benimassot": ("benimassot",),
    "Cocentaina": ("cocentaina",),
    "Fageca": ("facheca", "fageca"),
    "Famorca": ("famorca",),
    "Gaianes": ("gaianes",),
    "Gorga": ("gorga",),
    "Lorcha": ("l'orxa", "lorcha"),
    "Millena": ("millena",),
    "Muro de Alcoy": ("muro de alcoy", "muro d'alcoi"),
    "Planes": ("planes",),
    "Quatretondeta": ("quatretondeta",),
    "Tollos": ("tollos",),
    # Baix Segura / Vega Baja
    "Albatera": ("albatera",),
    "Algorfa": ("algorfa",),
    "Almoradí": ("almoradi",),
    "Benejúzar": ("benejuzar",),
    "Benferri": ("benferri",),
    "Benijófar": ("benijofar",),
    "Bigastro": ("bigastro",),
    "Callosa de Segura": ("callosa de segura",),
    "Catral": ("catral",),
    "Cox": ("cox",),
    "Daya Nueva": ("daya nueva",),
    "Daya Vieja": ("daya vieja",),
    "Dolores": ("dolores",),
    "Formentera del Segura": ("formentera del segura",),
    "Granja de Rocamora": ("granja de rocamora",),
    "Guardamar del Segura": ("guardamar del segura",),
    "Jacarilla": ("jacarilla",),
    "Los Montesinos": ("los montesinos",),
    "Orihuela": ("orihuela",),
    "Pilar de la Horadada": ("el pilar de la horadada", "pilar de la horadada"),
    "Rafal": ("rafal",),
    "Redován": ("redovan",),
    "Rojales": ("rojales",),
    "San Fulgencio": ("san fulgencio",),
    "San Isidro": ("san isidro",),
    "San Miguel de Salinas": ("san miguel de salinas",),
    "Torrevieja": ("torrevieja",),
}


def _compilar_variantes():
    """Aplana el dict canonico a una lista (variante_norm, canonico, patron)
    ordenada de variante MAS LARGA a mas corta, para que un nombre especifico
    gane siempre a uno contenido en el ("sant joan d'alacant" antes que
    "alacant", "muro de alcoy" antes que "alcoy"). Los nombres simples (una
    palabra) exigen limites de palabra para no confundir 'agost' dentro de
    otra palabra; los compuestos se buscan como subcadena directa."""
    pares = []
    for canonico, variantes in MUNICIPIOS_CANONICOS.items():
        for v in variantes:
            vn = _norm(v)
            if " " in vn or "'" in vn:
                pares.append((vn, canonico, None))
            else:
                pares.append((vn, canonico, re.compile(r"\b" + re.escape(vn) + r"\b")))
    pares.sort(key=lambda p: len(p[0]), reverse=True)
    return pares


_VARIANTES_COMPILADAS = _compilar_variantes()

# Set plano de variantes normalizadas: es lo que usa el filtro es_alicante
# (mismo contenido que la antigua lista plana _MUNICIPIOS_RAW).
_MUNICIPIOS = frozenset(vn for vn, _, _ in _VARIANTES_COMPILADAS)

# Indices para resolver un nombre escrito por el usuario a su canonico.
_CANONICO_POR_VARIANTE = {vn: canonico for vn, canonico, _ in _VARIANTES_COMPILADAS}
_CANONICO_POR_NORM = {_norm(c): c for c in MUNICIPIOS_CANONICOS}

# Marcadores directos de provincia (cuando el texto lo dice explicitamente).
_MARCADORES = tuple(_norm(m) for m in (
    "alicante", "alacant", "provincia de alicante", "provincia d'alacant",
))

# Diputacion de Alicante y sus organismos son de la provincia por definicion.
_MARCADORES_ENTIDAD = tuple(_norm(m) for m in (
    "diputacion de alicante", "diputacion provincial de alicante",
    "excma. diputacion provincial de alicante", "suma gestion tributaria",
))

# Menciones provinciales que NO son un municipio: se eliminan del texto antes
# de buscar el municipio, para que "Diputacion de Alicante" o "Boletin
# Oficial de la Provincia de Alicante" no se asignen al municipio "Alicante".
# El orden importa: las formas largas van antes que las cortas que contienen.
_MARCADORES_NO_MUNICIPIO_RE = re.compile(
    "|".join(re.escape(m) for m in (
        "excma. diputacion provincial de alicante",
        "diputacion provincial de alicante",
        "diputacion de alicante",
        "boletin oficial de la provincia de alicante",
        "provincia de alicante",
        "provincia d'alacant",
        "suma gestion tributaria",
    ))
)


def _contiene_municipio(texto_norm: str) -> bool:
    # Match por palabra/segmento: buscamos el nombre del municipio como
    # subcadena delimitada para no confundir 'agost' dentro de otra palabra.
    for muni, _, patron in _VARIANTES_COMPILADAS:
        if patron is None:
            if muni in texto_norm:
                return True
        elif patron.search(texto_norm):
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


def municipio_de(entidad: str = "", titulo: str = "") -> str | None:
    """Municipio canonico al que pertenece un anuncio, o None.

    Mira primero la entidad y, si ahi no hay municipio, el titulo. Antes de
    buscar elimina las menciones provinciales que no son un municipio (la
    Diputacion, "provincia de Alicante"...): una bolsa de la Diputacion sin
    municipio en el titulo devuelve None, no "Alicante". Las variantes se
    prueban de mas larga a mas corta para que "Muro de Alcoy" no se asigne
    a "Alcoy" ni "Sant Joan d'Alacant" a "Alicante"."""
    for texto in (entidad, titulo):
        t = _MARCADORES_NO_MUNICIPIO_RE.sub(" ", _norm(texto or ""))
        if not t.strip():
            continue
        for vn, canonico, patron in _VARIANTES_COMPILADAS:
            if patron is None:
                if vn in t:
                    return canonico
            elif patron.search(t):
                return canonico
    return None


def resolver_municipio(nombre) -> str | None:
    """Resuelve un nombre escrito por el usuario ("elx", "ELCHE",
    "Villajoyosa") al municipio canonico, o None si no corresponde a ningun
    municipio de la provincia. Insensible a mayusculas y acentos."""
    n = _norm((nombre or "").strip())
    if not n:
        return None
    return _CANONICO_POR_NORM.get(n) or _CANONICO_POR_VARIANTE.get(n)


def lista_municipios() -> list:
    """Nombres canonicos de todos los municipios, orden alfabetico
    (ignorando acentos, para que 'Dénia' no caiga despues de la zeta)."""
    return sorted(MUNICIPIOS_CANONICOS, key=_norm)
