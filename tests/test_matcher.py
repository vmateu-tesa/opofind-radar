"""Test de core/matcher.py contra los perfiles reales de config/alertas.yaml."""

from core.matcher import Matcher


def test_carga_los_perfiles_reales():
    m = Matcher()
    nombres = [p.get("nombre") for p in m.perfiles]
    assert "Informatica_Telecom" in nombres
    assert "Docencia_Secundaria_FP" in nombres
    assert "Global_Provincia" in nombres


def test_match_informatica_telecom():
    m = Matcher()
    matches = m.match("Tecnico de Sistemas de Informacion y Telecomunicaciones")
    assert "Informatica_Telecom" in matches


def test_match_docencia():
    m = Matcher()
    matches = m.match("Profesor de Secundaria - Formacion Profesional")
    assert "Docencia_Secundaria_FP" in matches


def test_exclusion_tiene_prioridad():
    m = Matcher()
    # "turismo" esta en las exclusiones de Informatica_Telecom.
    matches = m.match("Tecnico Informatico - Departamento de Turismo")
    assert "Informatica_Telecom" not in matches


def test_perfil_global_matchea_todo_salvo_exclusiones():
    m = Matcher()
    matches = m.match("Peon de jardineria municipal")
    assert "Global_Provincia" in matches

    matches_excluido = m.match("Enfermero de atencion primaria")
    assert "Global_Provincia" not in matches_excluido


def test_texto_vacio_no_matchea_nada():
    m = Matcher()
    assert m.match("") == []
    assert m.match(None) == []
