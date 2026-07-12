"""Tests del scraper del DOGV (offline, sobre una respuesta real guardada).

La fixture mezcla organismos de la provincia de Alicante (Castalla) con
otros de Valencia y Castellon: el filtro es_alicante debe dejar solo los de
Alicante.
"""

import json
import os

import pytest

from scrapers.dogv import DogvScraper

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "dogv_search.json")


@pytest.fixture
def data():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_filtra_solo_provincia_de_alicante(data, monkeypatch):
    scraper = DogvScraper()
    # Servimos la fixture en la primera pagina y una pagina vacia despues.
    llamadas = {"n": 0}

    def fake_fetch(inicio, fin, page):
        return data if page == 0 else {"totalPages": 1, "content": []}

    monkeypatch.setattr(scraper, "_fetch_pagina", fake_fetch)
    items = scraper.scrape()

    entidades = {c.entidad for c in items}
    assert any("Castalla" in e for e in entidades)
    # Nada de Valencia / Castellon.
    assert not any("Val" in e or "Castell" in e or "Picanya" in e for e in entidades)


def test_mapea_campos_dogv(data):
    scraper = DogvScraper()
    castalla = next(i for i in data["content"] if "Castalla" in (i.get("organismo") or ""))
    conv = scraper._parse_item(castalla)
    assert conv is not None
    assert conv.fuente == "dogv"
    assert conv.entidad == "Ayuntamiento de Castalla"
    assert conv.id_origen.startswith("dogv-")
    assert conv.enlace.startswith("https://dogv.gva.es/es/resultat-dogv?signatura=")


def test_item_fuera_de_alicante_devuelve_none(data):
    scraper = DogvScraper()
    valencia = next(i for i in data["content"] if "Val" in (i.get("organismo") or ""))
    assert scraper._parse_item(valencia) is None


def test_item_sin_codigo_o_titulo_se_descarta():
    scraper = DogvScraper()
    assert scraper._parse_item({"organismo": "Ayuntamiento de Elche", "titulo": ""}) is None
    assert scraper._parse_item({"organismo": "Ayuntamiento de Elche", "codigoInsercion": ""}) is None
