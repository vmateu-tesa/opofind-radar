"""Tests del motor de coincidencias multi-perfil (app/matcher.py).

Los perfiles se cargan de verdad desde config/alertas.yaml vía
app.config.load_profiles(), para que estos tests detecten roturas si
alguien cambia los patrones reales sin darse cuenta.
"""

import pytest

from app.config import load_profiles
from app.matcher import evaluate


@pytest.fixture(scope="module")
def profiles():
    return load_profiles()


def test_no_falso_positivo_tic_en_practica(profiles):
    """Regresión: 'práctica administrativa' NO debe activar telecomunicaciones_tic
    solo porque 'tic' es substring de 'practica'. El patrón usa \\btic\\b
    (word-boundary), que no debe matchear en medio de la palabra 'practica'."""
    anuncio = {
        "plaza": "Auxiliar de práctica administrativa",
        "entidad": "Ayuntamiento de Benidorm",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "telecomunicaciones_tic" not in coincidencias


def test_match_telecomunicaciones_tic(profiles):
    anuncio = {
        "plaza": "Técnico/a Superior de Telecomunicaciones",
        "entidad": "Diputación de Alicante",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "telecomunicaciones_tic" in coincidencias


def test_match_iot_smartcity(profiles):
    anuncio = {
        "plaza": "Técnico en Smart City e IoT",
        "entidad": "Ayuntamiento de Alicante",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "iot_automatizacion_smartcity" in coincidencias


def test_match_acustica(profiles):
    anuncio = {
        "plaza": "Ingeniero/a especialista en Acústica",
        "entidad": "Ayuntamiento de Benidorm",
        "obs": "Contaminación acústica municipal",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "acustica" in coincidencias


def test_match_docencia_fp_secundaria(profiles):
    anuncio = {
        "plaza": "Profesor/a de Secundaria - Tecnología",
        "entidad": "Conselleria de Educación",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "docencia_fp_secundaria" in coincidencias


def test_match_multiples_perfiles_simultaneos(profiles):
    """Un mismo anuncio puede interesar a más de un perfil a la vez: evaluate
    no debe quedarse con el primero que encuentre."""
    anuncio = {
        "plaza": "Técnico de Gestión de Sistemas de Información",
        "entidad": "Diputación de Alicante",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "telecomunicaciones_tic" in coincidencias
    assert "gestion_proyectos_admin_electronica" in coincidencias


def test_exclude_any_tiene_prioridad_sobre_include_any(profiles):
    """ingenieria_general incluye 'ingenier.{0,5}(tecnico|superior|industrial)'
    pero excluye ramas agrícola/forestal/minas/montes/agronómica/naval. Un
    ingeniero técnico agrícola coincide con el include, pero debe quedar
    excluido igualmente porque exclude_any manda."""
    anuncio = {
        "plaza": "Ingeniero Técnico Agrícola",
        "entidad": "Diputación de Alicante",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "ingenieria_general" not in coincidencias


def test_match_ingenieria_general_sin_exclusion(profiles):
    anuncio = {
        "plaza": "Ingeniero Técnico Industrial",
        "entidad": "Ayuntamiento de Alicante",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "ingenieria_general" in coincidencias


def test_ingenieria_general_solo_mira_campo_plaza(profiles):
    """ingenieria_general declara fields: [plaza] -- un término que solo
    aparece en entidad/obs no debe activarlo."""
    anuncio = {
        "plaza": "Auxiliar Administrativo",
        "entidad": "Escuela de Ingeniería Técnica Industrial",
        "obs": "",
    }
    coincidencias = evaluate(anuncio, profiles)
    assert "ingenieria_general" not in coincidencias


def test_anuncio_sin_coincidencias():
    perfiles_sinteticos = [
        {
            "name": "solo_pruebas",
            "fields": ["plaza"],
            "include_any": [r"\bpalabra_muy_rara\b"],
            "exclude_any": [],
        }
    ]
    anuncio = {"plaza": "Auxiliar Administrativo", "entidad": "", "obs": ""}
    assert evaluate(anuncio, perfiles_sinteticos) == []


def test_campos_ausentes_en_el_dict_no_rompen_evaluate():
    """Si el dict del anuncio no trae alguna de las claves usadas en 'fields'
    (p.ej. viene de una fuente que no rellena 'obs'), evaluate no debe fallar
    con KeyError."""
    perfiles_sinteticos = [
        {
            "name": "perfil_prueba",
            "fields": ["plaza", "entidad", "obs"],
            "include_any": ["informatic"],
            "exclude_any": [],
        }
    ]
    anuncio = {"plaza": "Técnico Informático"}  # sin 'entidad' ni 'obs'
    assert evaluate(anuncio, perfiles_sinteticos) == ["perfil_prueba"]
