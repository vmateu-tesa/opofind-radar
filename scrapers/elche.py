"""Scraper de la seccion de RRHH del Ayuntamiento de Elche (oposiciones y
procesos selectivos), via la API REST publica de WordPress (wp-json).

La web https://www.elche.es/recursos-humanos/oferta-publica-de-empleo/ es un
WordPress con una pagina hija por proceso selectivo (336 y subiendo, desde
2020). En vez de raspar el HTML publico (~177KB por oferta, con menu y footer
que meten ruido), se usa la API:

    GET /wp-json/wp/v2/pages?parent=3275&orderby=modified&order=desc
        &per_page=40&_fields=id,slug,link,title,modified,date,content

(3275 = id de la pagina indice "Oposiciones. Procesos selectivos."). Una
UNICA peticion devuelve las 40 ofertas modificadas mas recientemente CON su
content.rendered incluido, asi que el scraper hace 1 request por ejecucion
(muy por debajo del limite autoimpuesto de 1 peticion/segundo a elche.es).

LIMITE DE 40 OFERTAS (documentado a proposito): el catalogo completo son
~336 paginas que llegan hasta 2020, casi todas procesos ya cerrados que no
cambian nunca. Al ordenar por `modified` descendente, cualquier oferta NUEVA
(modified = fecha de creacion) o cualquier oferta vieja que EDITEN (nueva
noticia, fechas de examen...) entra automaticamente en la ventana de las 40
mas recientes, por lo que el cron diario no se pierde nada; solo se dejan
fuera fichas muertas sin cambios.

El content.rendered trae shortcodes [vc_*] de Visual Composer y HTML; se
limpia todo a texto plano y se extraen los campos con regex insensibles a
tildes (el texto real lleva PRESENTACIÓN, día...). Para no perder las tildes
en los valores almacenados, la normalizacion preserva las posiciones y los
valores se recortan del texto original con los spans del match.
"""

import html as html_lib
import re
import unicodedata
from typing import List, Optional

import requests

from scrapers.base import BaseScraper, ConvocatoriaData

API_URL = "https://www.elche.es/wp-json/wp/v2/pages"
PARENT_OPOSICIONES = 3275  # pagina indice "Oposiciones. Procesos selectivos."
HEADERS = {"User-Agent": "Mozilla/5.0"}

# --- Limpieza de content.rendered a texto plano ---
_RE_VC_SHORTCODE = re.compile(r"\[/?vc_[^\]]*\]")
_RE_SCRIPT = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)
_RE_STYLE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_ESPACIOS = re.compile(r"\s+")

# --- Extraccion de campos (se aplican sobre el texto NORMALIZADO: mayusculas
# y sin tildes, con las mismas posiciones que el texto original) ---

# Titulo: "NOMBRE PLAZA: X" o "NOMBRE PUESTO: X" (hay fichas con cada
# variante, incluso con texto extra antes de los dos puntos, p.ej.
# "NOMBRE PUESTO / NUMERO DE PUESTOS:"). El valor termina donde empieza el
# siguiente campo (NUMERO DE PLAZAS/PUESTOS o GRUPO).
_RE_NOMBRE = re.compile(
    r"NOMBRE\s+(?:PLAZA|PUESTO)[^:]{0,60}:\s*(.{1,200}?)\s*"
    r"(?:NUMERO\s+DE\s+(?:PLAZAS|PUESTOS)|GRUPO\s*:)"
)

# Vacantes: numero o el literal BOLSA (bolsas de trabajo sin plazas fijas).
_RE_VACANTES = re.compile(r"NUMERO\s+DE\s+(?:PLAZAS|PUESTOS)\s*:\s*(\d+|BOLSA)")

# Grupo funcionarial (whitelist para no capturar texto arbitrario).
_RE_GRUPO = re.compile(r"GRUPO\s*:\s*(A1|A2|AP|B|C1|C2|E)\b")

# Plazo de instancias: dentro de una ventana tras "PLAZO DE PRESENTACION".
_RE_DESDE = re.compile(r"DESDE\s+EL\s+DIA\s*(\d{2}/\d{2}/\d{4})")
_RE_HASTA = re.compile(r"HASTA\s+EL\s+(?:DIA\s*)?(\d{2}/\d{2}/\d{4})")

# Fin del bloque NOTICIAS: la seccion siguiente es "BASES BASES:" (titulo de
# seccion + campo). Se busca sobre el texto ORIGINAL respetando mayusculas,
# porque una noticia puede decir "Publicada convocatoria y bases." y esa
# palabra en minusculas NO es el encabezado de seccion.
_RE_FIN_NOTICIAS = re.compile(r"BASES\s+BASES\s*:")
_RE_BASES_SUELTO = re.compile(r"(?<![A-ZÁÉÍÓÚÜÑ])BASES(?![A-ZÁÉÍÓÚÜÑ])")

# Las fichas rellenan las secciones vacias con parrafos de solo puntos, que
# tras limpiar el HTML quedan como ". . ." intercalados.
_RE_PUNTOS_SUELTOS = re.compile(r"(?:\s*\.){2,}")


def _texto_plano(contenido_html: str) -> str:
    """Convierte content.rendered (HTML + shortcodes de Visual Composer) en
    una sola linea de texto plano con espacios colapsados."""
    texto = _RE_VC_SHORTCODE.sub(" ", contenido_html or "")
    texto = _RE_SCRIPT.sub(" ", texto)
    texto = _RE_STYLE.sub(" ", texto)
    texto = _RE_TAG.sub(" ", texto)
    texto = html_lib.unescape(texto)
    return _RE_ESPACIOS.sub(" ", texto).strip()


def _normalizar(texto: str) -> str:
    """Version en MAYUSCULAS y sin tildes del texto, preservando la longitud
    y las posiciones caracter a caracter. Asi las regex pueden ser
    insensibles a acentos y los valores capturados se recortan del texto
    ORIGINAL (con sus tildes) usando los spans del match."""
    resultado = []
    for caracter in texto:
        base = unicodedata.normalize("NFKD", caracter)[0]
        mayuscula = base.upper()
        # .upper() puede devolver mas de un caracter (p.ej. ß -> SS); en ese
        # caso se conserva el original para no desalinear posiciones.
        resultado.append(mayuscula if len(mayuscula) == 1 else caracter)
    return "".join(resultado)


class ElcheScraper(BaseScraper):
    ENTIDAD = "Ayuntamiento de Elche"

    def __init__(self, max_ofertas: int = 40):
        # Ver docstring del modulo: 40 es suficiente porque se ordena por
        # fecha de modificacion y cualquier cambio reentra en la ventana.
        self.max_ofertas = max_ofertas

    # ------------------------------------------------------------------
    # Extraccion de campos sobre el texto plano de una ficha
    # ------------------------------------------------------------------

    def _extraer_titulo(self, texto: str, norm: str) -> Optional[str]:
        m = _RE_NOMBRE.search(norm)
        if not m:
            return None
        inicio, fin = m.span(1)
        return texto[inicio:fin].strip() or None

    def _extraer_vacantes(self, norm: str) -> str:
        m = _RE_VACANTES.search(norm)
        return m.group(1) if m else ""

    def _extraer_grupo(self, norm: str) -> str:
        m = _RE_GRUPO.search(norm)
        return m.group(1) if m else ""

    def _extraer_plazo(self, norm: str) -> tuple:
        """(fecha_inicio, fecha_fin) del PRIMER 'PLAZO DE PRESENTACION' del
        texto, en dd/mm/yyyy o '' si aun no estan publicadas.

        Se acota una ventana tras el encabezado porque mas abajo hay otros
        plazos con el mismo patron (PLAZO SUBSANACION, Plazo de Alegaciones)
        que NO deben capturarse; ademas, cuando el plazo cierra intercalan
        texto ('PLAZO DE PRESENTACION CERRADO PLAZO INSTANCIAS (Desde el
        dia...')  y en fichas recien publicadas viene vacio ('Desde el dia
        hasta el dia')."""
        idx = norm.find("PLAZO DE PRESENTACION")
        if idx == -1:
            return "", ""
        ventana = norm[idx : idx + 250]
        # Cortar la ventana antes de los plazos "ruidosos" posteriores.
        for corte in ("PLAZO SUBSANACION", "ALEGACIONES", "LISTAS PROVISIONALES"):
            pos = ventana.find(corte, len("PLAZO DE PRESENTACION"))
            if pos != -1:
                ventana = ventana[:pos]
        m_desde = _RE_DESDE.search(ventana)
        m_hasta = _RE_HASTA.search(ventana)
        return (m_desde.group(1) if m_desde else "", m_hasta.group(1) if m_hasta else "")

    def _extraer_noticias(self, texto: str, norm: str) -> str:
        """Bloque NOTICIAS de la ficha (avisos fechados tipo '¡NUEVO!
        02/07/2026 Cerrado plazo de instancias.' o '(02-04-26) Publicada
        convocatoria'). Crece con cada novedad, por lo que incluirlo en
        observaciones hace variar el hash y dispara la notificacion de
        'actualizado', igual que el campo Obs de la Diputacion."""
        idx = norm.find("NOTICIAS")
        if idx == -1:
            return ""
        inicio = idx + len("NOTICIAS")
        bloque_original = texto[inicio : inicio + 1500]

        # Fin del bloque: encabezado de la seccion BASES (en mayusculas en el
        # original) o, en su defecto, el primer shortcode residual '['.
        m_fin = _RE_FIN_NOTICIAS.search(bloque_original) or _RE_BASES_SUELTO.search(bloque_original)
        if m_fin:
            bloque_original = bloque_original[: m_fin.start()]
        elif "[" in bloque_original:
            bloque_original = bloque_original[: bloque_original.index("[")]

        noticias = _RE_PUNTOS_SUELTOS.sub(".", bloque_original).strip()
        return noticias.strip(" .")

    # ------------------------------------------------------------------

    def _parsear_oferta(self, item: dict) -> Optional[ConvocatoriaData]:
        slug = (item.get("slug") or "").strip()
        enlace = (item.get("link") or "").strip()
        if not slug and enlace:
            # Fallback: ultimo segmento del path de la URL.
            slug = enlace.rstrip("/").rsplit("/", 1)[-1]
        if not slug:
            return None

        titulo_api = _texto_plano((item.get("title") or {}).get("rendered") or "")

        # Descartar paginas-plantilla del CMS (observadas en la seccion
        # hermana de provision de puestos; por si aparecieran aqui).
        titulo_api_norm = _normalizar(titulo_api)
        if slug.startswith("plantilla") or "PLANTILLA" in titulo_api_norm or "PONER AQUI" in titulo_api_norm:
            return None

        texto = _texto_plano((item.get("content") or {}).get("rendered") or "")
        norm = _normalizar(texto)

        # Titulo: campo "NOMBRE PLAZA/PUESTO" de la ficha; si no matchea
        # (formato nuevo), el title de la API siempre existe y es descriptivo
        # (p.ej. "INGENIERO/A DE TELECOMUNICACIONES (BOLSA)").
        titulo = self._extraer_titulo(texto, norm) or titulo_api
        if not titulo:
            return None

        fecha_inicio, fecha_fin = self._extraer_plazo(norm)

        observaciones_partes = []
        noticias = self._extraer_noticias(texto, norm)
        if noticias:
            observaciones_partes.append(noticias)
        grupo = self._extraer_grupo(norm)
        if grupo:
            observaciones_partes.append(f"Grupo {grupo}")

        return ConvocatoriaData(
            id_origen=slug,
            fuente="elche",
            titulo=titulo,
            entidad=self.ENTIDAD,
            enlace=enlace,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            observaciones=" | ".join(observaciones_partes),
            vacantes=self._extraer_vacantes(norm),
        )

    def scrape(self) -> List[ConvocatoriaData]:
        params = {
            "parent": PARENT_OPOSICIONES,
            "per_page": self.max_ofertas,
            "orderby": "modified",
            "order": "desc",
            "_fields": "id,slug,link,title,modified,date,content",
        }
        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=20)
        response.raise_for_status()
        items = response.json()

        convocatorias = []
        for item in items or []:
            try:
                conv = self._parsear_oferta(item)
            except Exception as e:
                # Una ficha con formato inesperado no debe tumbar el resto.
                print(f"Error parseando oferta de Elche {item.get('slug', '?')}: {e}")
                continue
            if conv:
                convocatorias.append(conv)
        return convocatorias


if __name__ == "__main__":
    scraper = ElcheScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} ofertas del Ayuntamiento de Elche.")
    for r in resultados[:3]:
        print(r.model_dump_json(indent=2))
