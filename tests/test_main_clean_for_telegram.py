"""Test de regresion: main._clean_for_telegram.

Bug real encontrado validando en vivo: dip_bolsa_oferta.py trae
observaciones con HTML crudo del RSS (<strong>, <br />). Telegram con
parse_mode="HTML" solo admite un subconjunto de etiquetas -- <strong> y
<br/> no estan permitidas, asi que el mensaje entero se rechazaba (HTTP 400)
y la notificacion no llegaba nunca para esas convocatorias.
"""

from main import _clean_for_telegram


def test_convierte_br_en_salto_de_linea():
    texto = "Bases: 01/07/2026<br />Fecha inicio: 02/07/2026"
    resultado = _clean_for_telegram(texto)
    assert "<br" not in resultado
    assert "\n" in resultado


def test_elimina_etiquetas_no_soportadas_por_telegram():
    texto = "<strong>Bases: </strong>01/07/2026<br /><strong>Fecha final:</strong> 15/07/2026"
    resultado = _clean_for_telegram(texto)
    assert "<strong>" not in resultado
    assert "</strong>" not in resultado
    assert "Bases:" in resultado
    assert "01/07/2026" in resultado


def test_escapa_ampersand_suelto():
    resultado = _clean_for_telegram("Ayuntamiento A & B")
    assert "&amp;" in resultado


def test_texto_vacio_no_rompe():
    assert _clean_for_telegram("") == ""
    assert _clean_for_telegram(None) is None


def test_texto_sin_html_no_cambia_de_forma_relevante():
    resultado = _clean_for_telegram("Tecnico Informatico")
    assert "Tecnico Informatico" in resultado
