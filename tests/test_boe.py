"""Tests offline del scraper del BOE (app/scrapers/boe.py).

No golpean la red: `requests.get` se sustituye por un doble que sirve el
fixture guardado en tests/fixtures/boe_sumario_20260708.json para una fecha
concreta y devuelve 404 (sin boletín) para el resto, replicando el
comportamiento real observado en la API del BOE.
"""

import datetime as dt
import json
import os

import pytest

from app.scrapers import boe

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "boe_sumario_20260708.json")


def _load_fixture() -> dict:
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None):
        self.status_code = status_code
        self._payload = payload
        self.text = "" if payload is None else json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 404:
            raise boe.requests.HTTPError(f"status {self.status_code}")


@pytest.fixture(autouse=True)
def _sin_rate_limit(monkeypatch):
    """Evita que los tests esperen de verdad el intervalo del RateLimiter."""
    monkeypatch.setattr(boe.boe_rate_limiter, "wait", lambda: None)


def test_as_list_normaliza_dict_lista_y_none():
    assert boe._as_list(None) == []
    assert boe._as_list({"a": 1}) == [{"a": 1}]
    assert boe._as_list([{"a": 1}, {"b": 2}]) == [{"a": 1}, {"b": 2}]


def test_procesar_sumario_extrae_solo_seccion_2b():
    data = _load_fixture()
    anuncios = boe._procesar_sumario(data)

    # 2 (lista) + 1 (epigrafe dict->item dict) + 1 (epigrafe dict->item dict) + 1 (sin epigrafe) = 5
    assert len(anuncios) == 5
    ids = {a.external_id for a in anuncios}
    # El item de la sección 2A (nombramiento individual) NO debe colarse.
    assert "BOE-A-2026-14700" not in ids
    assert ids == {
        "BOE-A-2026-14784",
        "BOE-A-2026-14785",
        "BOE-A-2026-14786",
        "BOE-A-2026-14790",
        "BOE-A-2026-14795",
    }


def test_anuncio_tiene_los_campos_esperados():
    data = _load_fixture()
    anuncios = boe._procesar_sumario(data)
    anuncio = next(a for a in anuncios if a.external_id == "BOE-A-2026-14784")

    assert anuncio.fuente == "boe"
    assert anuncio.entidad == "MINISTERIO DE LA PRESIDENCIA, JUSTICIA Y RELACIONES CON LAS CORTES"
    assert "libre designación" in anuncio.plaza
    assert anuncio.url_bases == "https://www.boe.es/boe/dias/2026/07/08/pdfs/BOE-A-2026-14784.pdf"
    assert anuncio.obs == ""
    assert anuncio.raw_data["_epigrafe"] == "Procedimientos de libre designación"
    assert anuncio.raw_data["control"] == "2026/10985"


def test_departamento_sin_epigrafe_intermedio_se_procesa():
    """Caso defensivo: departamento con "item" directo, sin "epigrafe" en medio."""
    data = _load_fixture()
    anuncios = boe._procesar_sumario(data)
    anuncio = next(a for a in anuncios if a.external_id == "BOE-A-2026-14795")

    assert anuncio.entidad == "AYUNTAMIENTO DE PRUEBA (sin epígrafe)"
    assert anuncio.raw_data.get("_epigrafe") is None


def test_fetch_salta_dias_sin_boletin_404(monkeypatch):
    """Simula 7 días: solo uno (hoy) tiene boletín con contenido; el resto 404."""
    fixture = _load_fixture()
    hoy = dt.date.today()
    fecha_con_boletin = hoy.strftime("%Y%m%d")

    llamadas = []

    def fake_get(url, headers=None, timeout=None):
        llamadas.append(url)
        assert headers.get("Accept") == "application/json"
        if fecha_con_boletin in url:
            return _FakeResponse(200, fixture)
        return _FakeResponse(404)

    monkeypatch.setattr(boe.requests, "get", fake_get)

    anuncios = boe.fetch(dias_atras=7)

    assert len(anuncios) == 5
    assert len(llamadas) == 7  # se ha intentado un día por cada uno de los 7


def test_fetch_respeta_dias_atras(monkeypatch):
    """Con dias_atras=1 solo se consulta el día de hoy."""
    llamadas = []

    def fake_get(url, headers=None, timeout=None):
        llamadas.append(url)
        return _FakeResponse(404)

    monkeypatch.setattr(boe.requests, "get", fake_get)

    anuncios = boe.fetch(dias_atras=1)

    assert anuncios == []
    assert len(llamadas) == 1


def test_fetch_continua_si_un_dia_falla_por_error_de_red(monkeypatch):
    """Un RequestException en un día concreto no debe abortar el resto."""
    fixture = _load_fixture()
    hoy = dt.date.today()
    fecha_con_boletin = hoy.strftime("%Y%m%d")
    fecha_ayer = (hoy - dt.timedelta(days=1)).strftime("%Y%m%d")

    def fake_get(url, headers=None, timeout=None):
        if fecha_ayer in url:
            raise boe.requests.ConnectionError("fallo de red simulado")
        if fecha_con_boletin in url:
            return _FakeResponse(200, fixture)
        return _FakeResponse(404)

    monkeypatch.setattr(boe.requests, "get", fake_get)

    anuncios = boe.fetch(dias_atras=3)

    assert len(anuncios) == 5


def test_item_sin_identificador_o_titulo_se_descarta():
    item_incompleto = {"identificador": "", "titulo": "Algo"}
    assert boe._parse_item(item_incompleto, "Entidad", "") is None

    item_sin_titulo = {"identificador": "BOE-A-2026-99999", "titulo": ""}
    assert boe._parse_item(item_sin_titulo, "Entidad", "") is None
