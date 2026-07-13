"""Scraper del Diari Oficial de la Generalitat Valenciana (DOGV), seccion
"II.A) Ofertas de empleo publico, oposiciones y concursos", via la API REST
JSON del portal oficial.

Los RSS clasicos del DOGV estan MUERTOS (responden 403), asi que se usa el
mismo endpoint de busqueda que consume el buscador de la web nueva:

    POST https://dogv.gva.es/dogv-portal/dogv/search
         ?lang=es_es&page=0&size=100&sort=fechaPublicacion,desc
    body JSON: {
        "seccionId": [28],            # subseccion "A) Ofertas de empleo
                                      #   publico, oposiciones y concursos"
        "isSeccion": false,
        "fechaInicioPublicacion": "dd-MM-yyyy",
        "fechaFinPublicacion":    "dd-MM-yyyy"
    }

La respuesta es paginada: {totalElements, totalPages, content: [...]}. Con
size=100 una semana entera cabe en una sola pagina (unos 70 items), pero se
itera por paginas por si un rango grande (backfill) supera las 100 filas.

De cada item del sumario NO se puede sacar el plazo de presentacion: eso
esta en el texto de la disposicion (el PDF), que a proposito NO se descarga
por item para no disparar N peticiones. Por eso fecha_inicio/fecha_fin van
vacias; el plazo real se resolveria en el futuro leyendo la disposicion.

Confirmado en vivo: ayuntamientos de la provincia de Alicante publican aqui
los extractos de sus bases (Sax, Orihuela, Petrer, Universidad de Alicante...).
La seccion 28 ya es "oposiciones y concursos", asi que apenas hay ruido y no
se filtra por relevancia (de eso se encarga el matcher).
"""

import datetime as dt
import os
import time
from typing import List, Optional

import requests

from scrapers.base import BaseScraper, ConvocatoriaData
from core.geo import es_alicante

SEARCH_URL = "https://dogv.gva.es/dogv-portal/dogv/search"

# id de la subseccion "A) Ofertas de empleo publico, oposiciones y concursos"
# (aparece en cada item como subseccion.id == 28).
SECCION_OFERTAS_EMPLEO = 28

PAGE_SIZE = 100

ENTIDAD_POR_DEFECTO = "Generalitat Valenciana / DOGV"

# Pausa entre peticiones de paginas para respetar ~1 req/s.
PAUSA_ENTRE_PAGINAS = 1.0


class DogvScraper(BaseScraper):
    def __init__(self, dias_atras: Optional[int] = None):
        # Rango [hoy - dias_atras, hoy], igual que BopAlicanteScraper. El cron
        # diario solo necesita 1-2 dias; se deja configurable via env para
        # poder hacer un backfill puntual sin tocar codigo.
        if dias_atras is None:
            try:
                dias_atras = int(os.getenv("DOGV_DIAS_ATRAS", "7"))
            except (TypeError, ValueError):
                dias_atras = 7
        self.dias_atras = max(0, dias_atras)

    def _fetch_pagina(self, inicio: dt.date, fin: dt.date, page: int) -> Optional[dict]:
        params = {
            "lang": "es_es",
            "page": page,
            "size": PAGE_SIZE,
            "sort": "fechaPublicacion,desc",
        }
        body = {
            "seccionId": [SECCION_OFERTAS_EMPLEO],
            "isSeccion": False,
            "fechaInicioPublicacion": inicio.strftime("%d-%m-%Y"),
            "fechaFinPublicacion": fin.strftime("%d-%m-%Y"),
        }
        response = requests.post(SEARCH_URL, params=params, json=body, timeout=20)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return None
        return data

    def _parse_item(self, item: dict) -> Optional[ConvocatoriaData]:
        # Se descartan borradores (no publicados). El buscador publico no
        # deberia devolverlos, pero es una guarda barata.
        if item.get("borrador"):
            return None

        codigo = (item.get("codigoInsercion") or "").strip()
        titulo = (item.get("titulo") or "").strip()
        # Sin codigoInsercion no hay id estable ni enlace publico; sin titulo
        # no hay nada que mostrar ni matchear.
        if not codigo or not titulo:
            return None

        organismo = (item.get("organismo") or "").strip()
        entidad = organismo or ENTIDAD_POR_DEFECTO

        # La app se centra SOLO en la provincia de Alicante, pero el DOGV
        # cubre toda la Comunidad Valenciana. Se descarta lo que no sea de
        # Alicante (el organismo suele decir el ayuntamiento; si no, el titulo).
        if not es_alicante(organismo, titulo):
            return None

        enlace = f"https://dogv.gva.es/es/resultat-dogv?signatura={codigo}"

        # Observaciones estables (numero de DOGV y fecha de publicacion). No
        # cambian salvo correccion, asi que no ensucian el hash con ruido.
        obs_parts = []
        num_dogv = str(item.get("numeroDogv") or "").strip()
        fecha_pub = (item.get("fechaPublicacion") or "").strip()
        if num_dogv:
            obs_parts.append(f"DOGV nº{num_dogv}")
        if fecha_pub:
            obs_parts.append(f"publicado {fecha_pub}")

        return ConvocatoriaData(
            id_origen=f"dogv-{codigo}",
            fuente="dogv",
            titulo=titulo,
            entidad=entidad,
            enlace=enlace,
            # El sumario no da plazo; se deja vacio (ver docstring del modulo).
            fecha_inicio="",
            fecha_fin="",
            observaciones=" · ".join(obs_parts),
            vacantes="",
        )

    def scrape(self) -> List[ConvocatoriaData]:
        hoy = dt.date.today()
        inicio = hoy - dt.timedelta(days=self.dias_atras)

        convocatorias: List[ConvocatoriaData] = []
        vistos: set = set()

        page = 0
        total_pages = 1  # se ajusta con la respuesta de la primera pagina
        while page < total_pages:
            if page > 0:
                # Rate limit: solo se espera si de verdad hay mas de una pagina.
                time.sleep(PAUSA_ENTRE_PAGINAS)
            try:
                data = self._fetch_pagina(inicio, hoy, page)
            except Exception as e:
                print(f"Error consultando DOGV (pagina {page}): {e}")
                break

            if data is None:
                break

            total_pages = int(data.get("totalPages") or 1)

            for item in data.get("content") or []:
                try:
                    conv = self._parse_item(item)
                except Exception as e:
                    print(f"Error parseando item de DOGV {item.get('codigoInsercion', '?')}: {e}")
                    continue
                if conv is None:
                    continue
                # Dedup por si el mismo codigo apareciese en dos paginas.
                if conv.id_origen in vistos:
                    continue
                vistos.add(conv.id_origen)
                convocatorias.append(conv)

            page += 1

        return convocatorias


if __name__ == "__main__":
    scraper = DogvScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} convocatorias en DOGV (ofertas de empleo publico).")
    for r in resultados[:3]:
        print(r.model_dump_json(indent=2))
