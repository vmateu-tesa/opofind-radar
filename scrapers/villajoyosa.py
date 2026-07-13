"""Scraper de "Ofertas de empleo" del Ayuntamiento de la Vila Joiosa
(Villajoyosa), Marina Baixa.

Su sede Gestiona (sedelectronica.es) esta sin configurar ("Sede Electronica
Indeterminada"), asi que el ayuntamiento publica en su propia web WordPress
(Elementor + JetEngine): https://www.villajoyosa.com/ofertas-de-empleo/

Cada convocatoria es un bloque `.jet-listing-grid__item` con atributo
`data-post-id` (id numerico ESTABLE de WordPress) y, dentro, texto plano sin
headings: "<fecha> <titulo> <descripcion>" seguido de un enlace "Descargar
Bases...". La pagina lista TODO el historico (cientos de items), asi que se
limita a los N mas recientes (por orden de aparicion, que ya viene de mas
reciente a mas antiguo).

Villajoyosa ademas remite a un portal externo "Convoca" (SPA con login
OAuth, sin API publica facil de consumir) para inscripciones -- no se usa
aqui, solo la propia pagina de ofertas.
"""

import re
from typing import List
from urllib.parse import urljoin

import requests

from scrapers.base import BaseScraper, ConvocatoriaData

URL = "https://www.villajoyosa.com/ofertas-de-empleo/"
ENTIDAD = "Ayuntamiento de la Vila Joiosa / Villajoyosa"

# La pagina no pagina: lista todo el historico en una sola carga. Nos
# quedamos solo con los N mas recientes (vienen en ese orden).
MAX_ITEMS = 40

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OpoRadarBot/1.0; +uso personal)"}
_FECHA_RE = re.compile(
    r"^\s*(\d{1,2}\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+20\d\d)\s*", re.I,
)


def _parse_listado(html: str) -> List[ConvocatoriaData]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    resultado = []
    for item in soup.select(".jet-listing-grid__item")[:MAX_ITEMS]:
        post_id = item.get("data-post-id", "").strip()
        texto = item.get_text(" ", strip=True)
        if not texto:
            continue

        m = _FECHA_RE.match(texto)
        fecha_pub = ""
        resto = texto
        if m:
            fecha_pub = m.group(1)
            resto = texto[m.end():]

        # El titulo es la primera "frase" del resto (hasta el primer punto
        # seguido de mayuscula/espacio largo, o los primeros ~140 caracteres
        # si no se distingue bien del cuerpo). Es una heuristica: el
        # descriptivo real puede ser largo, asi que se recorta con criterio.
        titulo = resto.split(".")[0].strip() if resto else ""
        if not titulo or len(titulo) > 180:
            titulo = resto[:140].strip()
        if not titulo:
            continue

        enlace_tag = item.find("a", href=True)
        href = enlace_tag["href"] if enlace_tag else ""
        enlace = urljoin(URL, href) if href else URL

        id_origen = f"villajoyosa-{post_id}" if post_id else f"villajoyosa-{titulo[:40]}"

        resultado.append(
            ConvocatoriaData(
                id_origen=id_origen,
                fuente="villajoyosa",
                titulo=titulo,
                entidad=ENTIDAD,
                enlace=enlace,
                fecha_inicio="",   # el plazo esta en el PDF de bases, no en el listado
                fecha_fin="",
                observaciones=f"Publicado {fecha_pub}" if fecha_pub else "",
                vacantes="",
            )
        )
    return resultado


class VillajoyosaScraper(BaseScraper):
    def scrape(self) -> List[ConvocatoriaData]:
        try:
            r = requests.get(URL, timeout=20, headers=_HEADERS)
            r.raise_for_status()
        except Exception as e:
            print(f"Error tablon de ofertas de Villajoyosa: {e}")
            return []
        return _parse_listado(r.text)


if __name__ == "__main__":
    items = VillajoyosaScraper().scrape()
    print(f"Ofertas de empleo de Villajoyosa: {len(items)}")
    for c in items[:10]:
        print(f"  - [{c.id_origen}] {c.titulo[:65]}")
