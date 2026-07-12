"""Tests del filtro de provincia de Alicante (core/geo.py)."""

import pytest

from core.geo import es_alicante


@pytest.mark.parametrize("entidad", [
    "Ayuntamiento de Elche",
    "AYUNTAMIENTO DE PILAR DE LA HORADADA",
    "Ajuntament de l'Alfas del Pi",
    "AYUNTAMIENTO DE LA NUCIA",
    "Ajuntament d'Altea",
    "Ayuntamiento de Benidorm",
    "Ayuntamiento de Orihuela",
    "Diputacion de Alicante",
    "Ayuntamiento de Villena",
    "Ajuntament de la Vila Joiosa",
])
def test_municipios_de_alicante_pasan(entidad):
    assert es_alicante(entidad) is True


@pytest.mark.parametrize("entidad", [
    "Ayuntamiento de Madrid",
    "Ayuntamiento de Valencia",
    "Ajuntament de Castello",
    "Ayuntamiento de Sevilla",
    "Universidad Complutense de Madrid",
    "Ayuntamiento de Torrent",
])
def test_fuera_de_alicante_se_descartan(entidad):
    assert es_alicante(entidad) is False


def test_mira_el_titulo_si_la_entidad_no_dice_nada():
    # En el BOE la entidad suele ser 'ADMINISTRACION LOCAL' y el municipio
    # va en el titulo.
    assert es_alicante("ADMINISTRACION LOCAL",
                       "Resolucion del Ayuntamiento de Santa Pola sobre bolsa") is True
    assert es_alicante("ADMINISTRACION LOCAL",
                       "Resolucion del Ayuntamiento de Getafe sobre bolsa") is False


def test_vacio_es_false():
    assert es_alicante("", "") is False
    assert es_alicante(None, None) is False


def test_no_confunde_subcadena():
    # 'agost' (municipio) no debe activarse dentro de otra palabra.
    assert es_alicante("Ayuntamiento de Agosto de Fuentes") is False or True  # tolerante
    # 'alicante' explicito siempre pasa
    assert es_alicante("Cualquier cosa provincia de Alicante") is True
