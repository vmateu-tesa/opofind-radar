"""Test offline del scraper de l'Alfas del Pi (sobre fixture HTML real)."""

import os

import pytest

from scrapers.alfaz import _parse_listado, AlfazScraper, ENTIDAD

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "alfaz_listado.html")


@pytest.fixture
def html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_enumera_entradas(html):
    items = _parse_listado(html)
    assert len(items) >= 5


def test_campos_de_cada_item(html):
    items = _parse_listado(html)
    c = items[0]
    assert c.fuente == "alfaz"
    assert c.entidad == ENTIDAD
    assert c.id_origen.startswith("alfaz-")
    assert c.titulo
    assert c.enlace.startswith("https://www.lalfas.es/")


def test_id_estable_por_post_id(html):
    # El id viene del post-<numero> de WordPress (estable aunque cambie el slug).
    items = _parse_listado(html)
    assert any(c.id_origen[len("alfaz-"):].isdigit() for c in items)


def test_ids_unicos(html):
    items = _parse_listado(html)
    ids = [c.id_origen for c in items]
    assert len(ids) == len(set(ids))


def test_todo_es_seleccion_de_personal(html):
    # La seccion sel_personal ya es solo empleo: los titulos hablan de
    # bolsas / procesos selectivos / convocatorias.
    items = _parse_listado(html)
    texto = " ".join(c.titulo.lower() for c in items)
    assert "bolsa" in texto or "proceso selectivo" in texto or "convocatoria" in texto


def test_listado_vacio_no_rompe():
    assert _parse_listado("<html><body>nada</body></html>") == []


def test_scraper_paginacion_para_al_repetirse(monkeypatch, html):
    # Si todas las paginas devuelven lo mismo, no debe duplicar ni bucle infinito.
    class _Resp:
        status_code = 200
        text = html
        def raise_for_status(self): pass
    monkeypatch.setattr("scrapers.alfaz.requests.get", lambda *a, **k: _Resp())
    monkeypatch.setattr("scrapers.alfaz.time.sleep", lambda *a, **k: None)
    items = AlfazScraper().scrape()
    ids = [c.id_origen for c in items]
    assert len(ids) == len(set(ids))  # sin duplicados
