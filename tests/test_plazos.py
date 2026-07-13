"""Tests del motor de plazos (core/plazos.py).

Todas las fechas se inyectan (hoy=...) para que sean deterministas. El caso
Elche real (Ingeniero/a de Telecomunicaciones, plazo 17/06/2026-01/07/2026)
esta cubierto explicitamente: es la razon de ser de este modulo.
"""

from datetime import date

import pytest

from core import plazos
from core.plazos import (
    parse_fecha, dias_restantes, estado_plazo, leer_umbrales, avisos_pendientes,
    PROXIMAMENTE, ABIERTO, CIERRA_PRONTO, CERRADO, SIN_FECHAS,
)

# Plazo real de la oferta que el usuario perdio.
ELCHE_INI = "17/06/2026"
ELCHE_FIN = "01/07/2026"


# --- parse_fecha -------------------------------------------------------------

def test_parse_fecha_formato_real():
    assert parse_fecha("17/06/2026") == date(2026, 6, 17)


def test_parse_fecha_tolera_separadores_y_una_cifra():
    assert parse_fecha("1-7-2026") == date(2026, 7, 1)
    assert parse_fecha(" 01.07.2026 ") == date(2026, 7, 1)


def test_parse_fecha_vacia_o_invalida_es_none():
    assert parse_fecha("") is None
    assert parse_fecha(None) is None
    assert parse_fecha("32/13/2026") is None
    assert parse_fecha("17/06/26") is None  # año de 2 cifras: ambiguo, descartado


def test_parse_fecha_acepta_date_directo():
    assert parse_fecha(date(2026, 7, 1)) == date(2026, 7, 1)


# --- estado_plazo: recorrido del caso Elche ---------------------------------

@pytest.mark.parametrize("hoy,esperado", [
    (date(2026, 6, 16), PROXIMAMENTE),   # vispera de apertura
    (date(2026, 6, 17), ABIERTO),        # primer dia
    (date(2026, 6, 25), ABIERTO),        # en curso, quedan mas de 5
    (date(2026, 6, 27), CIERRA_PRONTO),  # quedan 5 (contando hoy)
    (date(2026, 6, 30), CIERRA_PRONTO),  # penultimo dia
    (date(2026, 7, 1), CIERRA_PRONTO),   # ULTIMO dia: aun se puede presentar
    (date(2026, 7, 2), CERRADO),         # plazo pasado
])
def test_estado_plazo_caso_elche(hoy, esperado):
    assert estado_plazo(ELCHE_INI, ELCHE_FIN, hoy=hoy) == esperado


def test_estado_plazo_sin_fechas():
    assert estado_plazo("", "", hoy=date(2026, 6, 20)) == SIN_FECHAS
    assert estado_plazo(None, None, hoy=date(2026, 6, 20)) == SIN_FECHAS


def test_estado_plazo_solo_fin():
    # Sin fecha de inicio pero con fin futuro: se considera abierto.
    assert estado_plazo("", "01/07/2026", hoy=date(2026, 6, 20)) == ABIERTO
    assert estado_plazo("", "01/07/2026", hoy=date(2026, 7, 5)) == CERRADO


# --- dias_restantes ----------------------------------------------------------

def test_dias_restantes_no_cuenta_hoy():
    assert dias_restantes(ELCHE_FIN, hoy=date(2026, 7, 1)) == 0   # hoy ultimo dia
    assert dias_restantes(ELCHE_FIN, hoy=date(2026, 6, 26)) == 5
    assert dias_restantes(ELCHE_FIN, hoy=date(2026, 7, 2)) == -1


def test_dias_restantes_sin_fecha_es_none():
    assert dias_restantes("", hoy=date(2026, 6, 20)) is None


# --- leer_umbrales -----------------------------------------------------------

def test_leer_umbrales_default():
    assert leer_umbrales("") == [5, 1]


def test_leer_umbrales_parseo_robusto():
    assert leer_umbrales("5,1") == [5, 1]
    assert leer_umbrales("1;5; 3 ") == [5, 3, 1]
    assert leer_umbrales("basura, 7, x") == [7]
    assert leer_umbrales("nada valido") == [5, 1]  # vuelve al default


# --- avisos_pendientes: el nucleo del "no se te vuelve a pasar" --------------

def test_aviso_apertura_el_primer_dia():
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    assert avisos_pendientes(conv, set(), [5, 1], hoy=date(2026, 6, 17)) == ["apertura"]


def test_no_repite_apertura_si_ya_enviada():
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    avisos = avisos_pendientes(conv, {"apertura"}, [5, 1], hoy=date(2026, 6, 18))
    assert "apertura" not in avisos


def test_aviso_cierre_5d_cuando_quedan_5():
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    # El 26/06 quedan 5 dias: apertura (si no enviada) + cierre_5d.
    avisos = avisos_pendientes(conv, {"apertura"}, [5, 1], hoy=date(2026, 6, 26))
    assert avisos == ["cierre_5d"]


def test_solo_umbral_mas_urgente_no_ambos_a_la_vez():
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    # El ultimo dia quedan 0: aplica <=5 y <=1, pero solo debe salir el mas
    # pequeño (cierre_1d), nunca cierre_5d y cierre_1d juntos.
    avisos = avisos_pendientes(conv, {"apertura", "cierre_5d"}, [5, 1], hoy=date(2026, 7, 1))
    assert avisos == ["cierre_1d"]


def test_plazo_cerrado_no_genera_avisos():
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    assert avisos_pendientes(conv, set(), [5, 1], hoy=date(2026, 7, 2)) == []


def test_plazo_proximamente_no_genera_avisos():
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    assert avisos_pendientes(conv, set(), [5, 1], hoy=date(2026, 6, 16)) == []


def test_sin_fechas_no_genera_avisos():
    assert avisos_pendientes({"fecha_inicio": "", "fecha_fin": ""}, set(), [5, 1]) == []


def test_habria_avisado_a_tiempo_del_caso_elche():
    """La prueba que da sentido a todo: recorriendo el plazo dia a dia con el
    registro de avisos ya enviados, el sistema emite apertura al abrir y al
    menos un aviso de cierre antes de que expire -- nunca se habria escapado."""
    conv = {"fecha_inicio": ELCHE_INI, "fecha_fin": ELCHE_FIN}
    enviados = set()
    emitidos = []
    d = date(2026, 6, 17)
    while d <= date(2026, 7, 1):
        for aviso in avisos_pendientes(conv, enviados, [5, 1], hoy=d):
            enviados.add(aviso)
            emitidos.append((d.isoformat(), aviso))
        d = date.fromordinal(d.toordinal() + 1)
    tipos = {a for _, a in emitidos}
    assert "apertura" in tipos
    assert any(t.startswith("cierre_") for t in tipos)
