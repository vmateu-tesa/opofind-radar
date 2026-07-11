"""Test de core/classifier.py."""

from core.classifier import classify_tipo


def test_nombramiento():
    assert classify_tipo("NOMBRAMIENTO FUNCIONARIO DE CARRERA AGENTE POLICIA LOCAL") == "nombramiento"


def test_listas_admitidos():
    assert classify_tipo("LISTA PROVISIONAL ADMITIDOS/AS Y EXCLUIDOS/AS CONV. 26/11") == "listas"


def test_listas_tribunal():
    assert classify_tipo("Designacion del Tribunal Calificador") == "listas"


def test_plaza_desnuda_es_convocatoria_por_defecto():
    """La mayoria de filas de dip_otras_oposiciones son solo el nombre de la
    plaza, sin palabra clave -- estar en esa tabla ya implica convocatoria."""
    assert classify_tipo("Psicologo") == "convocatoria"
    assert classify_tipo("Agente de Igualdad") == "convocatoria"


def test_convocatoria_explicita():
    assert classify_tipo("Convocatoria de proceso selectivo para 2 plazas") == "convocatoria"
    assert classify_tipo("Bases de la convocatoria de bolsa de trabajo") == "convocatoria"


def test_texto_vacio_es_otros():
    assert classify_tipo("") == "otros"
    assert classify_tipo(None) == "otros"


def test_nombramiento_tiene_prioridad_sobre_listas():
    """Si un texto raro mezclase ambas señales, nombramiento (mas terminal)
    gana."""
    texto = "Lista definitiva y nombramiento de funcionario de carrera"
    assert classify_tipo(texto) == "nombramiento"
