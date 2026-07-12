"""Scraper del tablon de "Seleccion de Personal" del Ayuntamiento de
l'Alfas del Pi (WordPress con tema Divi).

l'Alfas es el pueblo del usuario. Su sede tiene el tablon Gestiona vacio
(usa esta web propia), asi que se raspa aqui directamente:
https://www.lalfas.es/list-transparencia/tablon-de-anuncios/sel_personal/

Es una lista paginada (/page/2/, /page/3/...) de <article> con clase
post-<id> (id numerico estable de WordPress), un titulo enlazado a la
pagina de detalle y una fecha en texto ("18 mayo 2026"). Como la propia
seccion ya es "seleccion de personal", TODO lo que aparece es empleo
publico: no hace falta filtrar por palabras clave.

El listado no da el plazo de instancias (esta dentro de cada convocatoria);
se deja fecha_inicio/fecha_fin vacias, igual que en los tablones Gestiona.
El BOP/DOGV cubren el plazo exacto, y el seguimiento avisa de cualquier
cambio.
"""

import re
import time
from typing import List
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, ConvocatoriaData

BASE_URL = "https://www.lalfas.es/list-transparencia/tablon-de-anuncios/sel_personal/"
ENTIDAD = "Ayuntamiento de l'Alfas del Pi"

# Numero maximo de paginas del listado a recorrer (las mas recientes). Cada
# pagina trae ~10 entradas; con 3 basta para el dia a dia.
MAX_PAGINAS = 3

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OpoRadarBot/1.0; +uso personal)"}
_POST_ID_RE = re.compile(r"\bpost-(\d+)\b")
_FECHA_RE = re.compile(
    r"\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+20\d\d", re.I,
)


def _parse_listado(html: str) -> List[ConvocatoriaData]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    resultado = []
    for art in soup.find_all("article"):
        clases = art.get("class") or []
        m = _POST_ID_RE.search(" ".join(clases))
        post_id = m.group(1) if m else None

        cabecera = art.find(["h1", "h2", "h3"])
        enlace_tag = cabecera.find("a") if cabecera else None
        titulo = (enlace_tag.get_text(strip=True) if enlace_tag
                  else (cabecera.get_text(strip=True) if cabecera else ""))
        if not titulo:
            continue
        href = enlace_tag["href"] if (enlace_tag and enlace_tag.has_attr("href")) else ""
        enlace = urljoin(BASE_URL, href) if href else BASE_URL

        # id estable: el post-<id> de WordPress; si faltara, el slug del enlace.
        if post_id:
            id_origen = f"alfaz-{post_id}"
        else:
            slug = href.rstrip("/").rsplit("/", 1)[-1] if href else titulo[:40]
            id_origen = f"alfaz-{slug}"

        fm = _FECHA_RE.search(art.get_text(" ", strip=True))
        fecha_pub = fm.group(0) if fm else ""

        resultado.append(
            ConvocatoriaData(
                id_origen=id_origen,
                fuente="alfaz",
                titulo=titulo,
                entidad=ENTIDAD,
                enlace=enlace,
                fecha_inicio="",   # el plazo esta en el detalle, no en el listado
                fecha_fin="",
                observaciones=f"Publicado {fecha_pub}" if fecha_pub else "",
                vacantes="",
            )
        )
    return resultado


class AlfazScraper(BaseScraper):
    def scrape(self) -> List[ConvocatoriaData]:
        resultado = []
        vistos = set()
        for page in range(1, MAX_PAGINAS + 1):
            url = BASE_URL if page == 1 else f"{BASE_URL}page/{page}/"
            try:
                r = requests.get(url, timeout=20, headers=_HEADERS)
                if r.status_code == 404:
                    break  # no hay mas paginas
                r.raise_for_status()
            except Exception as e:
                print(f"Error tablon de l'Alfas (pagina {page}): {e}")
                break

            items = _parse_listado(r.text)
            if not items:
                break
            nuevos = 0
            for c in items:
                if c.id_origen in vistos:
                    continue
                vistos.add(c.id_origen)
                resultado.append(c)
                nuevos += 1
            if nuevos == 0:
                break
            time.sleep(1)  # cortesia
        return resultado


if __name__ == "__main__":
    items = AlfazScraper().scrape()
    print(f"Seleccion de personal en l'Alfas del Pi: {len(items)}")
    for c in items[:12]:
        print(f"  - [{c.id_origen}] {c.titulo[:65]}")
