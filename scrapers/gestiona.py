"""Scraper generico del Tablon de anuncios de la plataforma Gestiona
(sedelectronica.es, de Espublico) para los ayuntamientos de la Marina Baixa.

La inmensa mayoria de municipios de la Marina Baixa publican su tablon en
https://<municipio>.sedelectronica.es/board, con un formato identico: una
tabla `table.AdvertisementBoardListPanel` cuyas filas tienen celdas con
clases fijas (class_name, class_folderCode, class_folderName,
class_boardCategory, class_description, class_dateFrom). Por eso UN solo
scraper parametrizado por (nombre, host) cubre todos los pueblos de golpe,
en vez de escribir uno por ayuntamiento.

El tablon mezcla todo tipo de anuncios (juntas de gobierno, urbanismo,
contratacion...). Nos quedamos solo con los de empleo publico: los que la
propia plataforma categoriza como "Empleo Publico" o cuyo texto suena a
proceso selectivo (mismo criterio amplio que el scraper del BOP).

Cobertura: los municipios sin actividad de empleo hoy no dan filas, pero
apareceran cuando publiquen. Villajoyosa y l'Alfas del Pi tienen el tablon
Gestiona vacio (usan otra via) y se cubren por otro lado (BOP / scraper
propio de Alfas).
"""

import re
import time
from typing import List
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, ConvocatoriaData

# (nombre para mostrar, subdominio en sedelectronica.es). Marina Baixa con
# tablon Gestiona funcional (verificado). Benidorm se excluye: ya tiene su
# propio scraper (eAdmin).
MARINA_BAIXA = [
    ("la Nucia", "lanucia"),
    ("Altea", "altea"),
    ("Finestrat", "finestrat"),
    ("Polop", "polop"),
    ("Callosa d'en Sarria", "callosadensarria"),
    ("Relleu", "relleu"),
    ("Orxeta", "orxeta"),
    ("Sella", "sella"),
    ("Tarbena", "tarbena"),
]

# La plataforma categoriza cada anuncio; "Empleo Publico" (y variantes) es
# la señal FIABLE de que es un proceso de personal. Es el filtro principal.
_CATEGORIA_EMPLEO_RE = re.compile(
    r"empleo\s*p[uú]blico|selecci[oó]n|seleccions|\bpersonal\b|recursos\s*humanos", re.I,
)

# Fallback por texto SOLO para terminos inequivocos de empleo, por si un
# pueblo publica bajo una categoria generica ("Anuncios"). Deliberadamente
# estricto: NO incluye "convocatoria" a secas (la usan tambien las Juntas de
# Gobierno, subvenciones, etc.), que era la causa de los falsos positivos.
_EMPLEO_STRICT_RE = re.compile(
    r"bolsa\s+de\s+(trabajo|empleo)|proceso\s+selectivo|oposici[oó]n|"
    r"concurso[\s-]oposici[oó]n|lista.{0,20}admitid|plaza.{0,10}vacante|"
    r"personal\s+laboral|oferta\s+de\s+empleo",
    re.I,
)

# Categorias/temas que NO son empleo aunque contengan palabras ambiguas.
_EXCLUIR_RE = re.compile(r"junta\s+de\s+gobierno|subvenci|padr[oó]n|matrimoni|registro\s+de\s+la\s+propiedad", re.I)

_UUID_RE = re.compile(r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OpoRadarBot/1.0; +uso personal)"}


def _celda(tr, clase):
    el = tr.select_one("." + clase)
    return el.get_text(" ", strip=True) if el else ""


def _es_empleo(categoria: str, titulo: str, descripcion: str) -> bool:
    texto = f"{titulo} {descripcion}"
    # La categoria oficial "Empleo Publico" manda (aunque el titulo sea generico).
    if categoria and _CATEGORIA_EMPLEO_RE.search(categoria):
        return True
    # Fuera de esa categoria, exige un termino inequivoco de empleo y que no
    # sea un tema claramente ajeno.
    if _EXCLUIR_RE.search(texto):
        return False
    return bool(_EMPLEO_STRICT_RE.search(texto))


def _parse_board(html: str, nombre: str, host: str) -> List[ConvocatoriaData]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tabla = soup.select_one("table.AdvertisementBoardListPanel")
    if not tabla:
        return []

    base_url = f"https://{host}.sedelectronica.es/board"
    resultado = []
    for tr in tabla.select("tbody tr"):
        if not tr.find_all("td"):
            continue
        nombre_doc = _celda(tr, "class_name")
        expediente = _celda(tr, "class_folderCode")
        procedimiento = _celda(tr, "class_folderName")
        categoria = _celda(tr, "class_boardCategory")
        descripcion = _celda(tr, "class_description")
        fecha_pub = _celda(tr, "class_dateFrom")

        # Titulo mas informativo: la descripcion del anuncio ("...bolsa de
        # empleo para el puesto de Conserje") dice mas que el nombre del
        # documento ("DECRETO 2026-0592") o el de la carpeta generica.
        titulo = descripcion or procedimiento or nombre_doc
        if not titulo:
            continue
        if not _es_empleo(categoria, f"{titulo} {procedimiento} {nombre_doc}", descripcion):
            continue

        enlace_tag = tr.select_one("a[href]")
        href = enlace_tag["href"] if enlace_tag else ""
        enlace = urljoin(base_url, href) if href else base_url

        m = _UUID_RE.search(href)
        ident = m.group(1) if m else (expediente or titulo)
        id_origen = f"gestiona-{host}-{ident}"

        obs_partes = []
        if categoria:
            obs_partes.append(categoria)
        if fecha_pub:
            obs_partes.append(f"Publicado {fecha_pub}")
        if nombre_doc and nombre_doc not in titulo:
            obs_partes.append(f"Documento: {nombre_doc}")

        resultado.append(
            ConvocatoriaData(
                id_origen=id_origen,
                fuente="gestiona",
                titulo=titulo,
                entidad=f"Ayuntamiento de {nombre}",
                enlace=enlace,
                fecha_inicio="",   # el tablon no da el plazo de instancias; va en el documento
                fecha_fin="",
                observaciones=" | ".join(obs_partes),
                vacantes="",
            )
        )
    return resultado


class GestionaScraper(BaseScraper):
    def __init__(self, municipios=None):
        self.municipios = municipios if municipios is not None else MARINA_BAIXA

    def scrape(self) -> List[ConvocatoriaData]:
        resultado = []
        for nombre, host in self.municipios:
            try:
                r = requests.get(
                    f"https://{host}.sedelectronica.es/board",
                    timeout=20, headers=_HEADERS,
                )
                r.raise_for_status()
                resultado.extend(_parse_board(r.text, nombre, host))
            except Exception as e:
                print(f"Error tablon Gestiona de {nombre} ({host}): {e}")
            time.sleep(1)  # cortesia: ~1 req/s
        return resultado


if __name__ == "__main__":
    items = GestionaScraper().scrape()
    print(f"Empleo publico en tablones Gestiona de la Marina Baixa: {len(items)}")
    for c in items[:12]:
        print(f"  - {c.entidad[:28]:28} | {c.titulo[:60]}")
