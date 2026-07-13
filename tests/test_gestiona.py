"""Tests del scraper generico de tablones Gestiona (Marina Baixa).

Offline: parsea una fixture HTML real del tablon de Callosa d'en Sarria.
"""

import os

import pytest

from scrapers.gestiona import _parse_board, _es_empleo, GestionaScraper, MARINA_BAIXA

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "gestiona_board_callosa.html")


@pytest.fixture
def board_html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_parsea_solo_empleo_publico(board_html):
    items = _parse_board(board_html, "Callosa d'en Sarria", "callosadensarria")
    assert items, "se esperaban anuncios de empleo en la fixture"
    # Todas las filas devueltas son de empleo (no juntas de gobierno ni subvenciones).
    for c in items:
        t = c.titulo.lower()
        assert "junta de gobierno" not in t
        assert "subvenci" not in t


def test_campos_de_cada_item(board_html):
    items = _parse_board(board_html, "Callosa d'en Sarria", "callosadensarria")
    c = items[0]
    assert c.fuente == "gestiona"
    assert c.entidad == "Ayuntamiento de Callosa d'en Sarria"
    assert c.id_origen.startswith("gestiona-callosadensarria-")
    assert c.enlace.startswith("https://callosadensarria.sedelectronica.es/")
    assert c.titulo


def test_ids_unicos(board_html):
    items = _parse_board(board_html, "Callosa", "callosadensarria")
    ids = [c.id_origen for c in items]
    assert len(ids) == len(set(ids))


def test_filtro_empleo():
    # Categoria oficial manda.
    assert _es_empleo("Empleo Publico", "Cualquier cosa", "") is True
    # Junta de gobierno NO es empleo aunque diga "convocatoria".
    assert _es_empleo("Anuncios", "Convocatoria de Junta de Gobierno Local", "") is False
    # Subvenciones NO.
    assert _es_empleo("Ayudas y Subvenciones", "Concesion de subvenciones", "") is False
    # Termino inequivoco en categoria generica SI.
    assert _es_empleo("Anuncios", "Bases del proceso selectivo de 2 plazas", "") is True
    assert _es_empleo("Anuncios", "Constitucion de bolsa de trabajo de conserje", "") is True


def test_tabla_ausente_no_rompe():
    assert _parse_board("<html><body>sin tabla</body></html>", "X", "x") == []


def test_config_marina_baixa_no_incluye_benidorm():
    # Benidorm tiene su propio scraper (eAdmin); no debe duplicarse aqui.
    hosts = [h for _, h in MARINA_BAIXA]
    assert "benidorm" not in hosts
    assert "lanucia" in hosts and "altea" in hosts
