"""Test offline del scraper de ofertas de empleo de Villajoyosa/la Vila
Joiosa (sobre fixture HTML real)."""

import os

import pytest

from scrapers.villajoyosa import _parse_listado, VillajoyosaScraper, ENTIDAD, MAX_ITEMS

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "villajoyosa_listado.html")


@pytest.fixture
def html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_enumera_entradas(html):
    items = _parse_listado(html)
    assert len(items) >= 5
    assert len(items) <= MAX_ITEMS


def test_campos_de_cada_item(html):
    items = _parse_listado(html)
    c = items[0]
    assert c.fuente == "villajoyosa"
    assert c.entidad == ENTIDAD
    assert c.id_origen.startswith("villajoyosa-")
    assert c.titulo
    assert c.enlace.startswith("https://www.villajoyosa.com/")


def test_id_estable_por_data_post_id(html):
    items = _parse_listado(html)
    assert any(c.id_origen[len("villajoyosa-"):].isdigit() for c in items)


def test_ids_unicos(html):
    items = _parse_listado(html)
    ids = [c.id_origen for c in items]
    assert len(ids) == len(set(ids))


def test_titulos_hablan_de_empleo(html):
    items = _parse_listado(html)
    texto = " ".join(c.titulo.lower() for c in items)
    assert any(k in texto for k in ("bolsa", "concurso", "oposicion", "plaza", "convocatoria"))


def test_listado_vacio_no_rompe():
    assert _parse_listado("<html><body>sin items</body></html>") == []


def test_scraper_maneja_error_de_red(monkeypatch):
    def fake_get(*a, **k):
        raise ConnectionError("simulado")
    monkeypatch.setattr("scrapers.villajoyosa.requests.get", fake_get)
    assert VillajoyosaScraper().scrape() == []
