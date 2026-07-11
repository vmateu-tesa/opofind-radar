"""Test offline de scrapers/dip_otras_oposiciones.py contra un HTML real
capturado de la web (data/investigacion/tabla_otras_oposiciones.html).

Cubre especificamente el bug que se encontro al validar en vivo: la celda
"Obs" no lleva texto plano, sino un <img title="..."> por cada publicacion
posterior (BOP/DOGV/BOE) de esa convocatoria -- un simple .get_text()
sobre esa celda siempre devuelve vacio.
"""

import os

import pytest

from scrapers.dip_otras_oposiciones import DipOtrasOposicionesScraper

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "investigacion", "tabla_otras_oposiciones.html")


class _FakeResponse:
    def __init__(self, content: bytes):
        self.content = content
        self.status_code = 200

    def raise_for_status(self):
        pass


@pytest.fixture
def resultados(monkeypatch):
    with open(FIXTURE_PATH, "rb") as f:
        html_bytes = f.read()

    def fake_get(url, timeout=None):
        return _FakeResponse(html_bytes)

    monkeypatch.setattr("scrapers.dip_otras_oposiciones.requests.get", fake_get)
    return DipOtrasOposicionesScraper().scrape()


def test_extrae_un_numero_razonable_de_filas(resultados):
    assert len(resultados) > 100


def test_todas_las_filas_tienen_plaza_y_entidad(resultados):
    for c in resultados:
        assert c.titulo.strip()
        assert c.entidad.strip()


def test_id_origen_viene_del_nombre_del_pdf(resultados):
    con_pdf = [c for c in resultados if ".pdf" in (c.enlace or "")]
    assert con_pdf, "se esperaban filas con enlace a PDF"
    for c in con_pdf:
        assert c.id_origen in c.enlace


def test_ids_son_unicos(resultados):
    ids = [c.id_origen for c in resultados]
    assert len(ids) == len(set(ids))


def test_obs_se_extrae_del_atributo_title_del_img(resultados):
    """Regresion del bug real: la celda Obs no tiene texto, tiene un <img
    title="..."> por publicacion. Antes del fix, observaciones era "" en el
    100% de las filas."""
    con_obs = [c for c in resultados if c.observaciones]
    assert con_obs, "se esperaban filas con Obs no vacio (bug de regresion)"
    # El contenido real del title suele mencionar el boletin de publicacion.
    assert any(
        "DOGV" in c.observaciones or "BOP" in c.observaciones or "BOE" in c.observaciones
        for c in con_obs
    )


def test_agente_de_igualdad_pilar_de_la_horadada(resultados):
    """Fila concreta conocida del fixture: valida plaza, entidad, vacantes,
    id del PDF y Obs exactos."""
    fila = next(
        (c for c in resultados if c.titulo == "Agente de Igualdad" and "Pilar de la Horadada" in c.entidad),
        None,
    )
    assert fila is not None
    assert fila.vacantes == "1"
    assert fila.id_origen == "11249"
    assert "Publica extracto bases" in fila.observaciones


def test_fila_sin_enlace_pdf_no_rompe_con_hashlib(monkeypatch):
    """Regresion del segundo bug real: sin `import hashlib`, cualquier fila
    sin enlace .pdf reconocible lanzaba NameError en el fallback de ID."""
    html = b"""
    <table>
      <tr><th>Plaza</th><th>Entidad</th><th>Vacantes</th><th>Bases</th>
          <th>F.Inicio</th><th>F.Final</th><th>Obs</th></tr>
      <tr>
        <td>Plaza de prueba</td><td>Entidad de prueba</td><td>1</td>
        <td>Sin enlace disponible</td><td></td><td></td><td></td>
      </tr>
    </table>
    """

    def fake_get(url, timeout=None):
        return _FakeResponse(html)

    monkeypatch.setattr("scrapers.dip_otras_oposiciones.requests.get", fake_get)
    resultados = DipOtrasOposicionesScraper().scrape()

    assert len(resultados) == 1
    assert resultados[0].id_origen  # no debe lanzar NameError, debe generar un hash
