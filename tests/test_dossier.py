"""Tests de app/dossier.py.

`find_similar_processes` se prueba contra una BD SQLite temporal (fichero
real en `tmp_path`, mismo esquema que app.db) con datos insertados
directamente por SQL -- sin red, sin scrapers reales.

`temario_references` hace comprobaciones HTTP en caliente (`_url_ok`) en cada
llamada, así que aquí se monkeypatchea para no depender de red real ni de
que boe.es esté arriba en el momento de correr los tests; el hecho de que las
URLs reales respondan 200 se comprobó a mano durante el desarrollo (ver
docstring del módulo)."""

import sqlite3

import pytest

from app.dossier import (
    build_dossier,
    find_similar_processes,
    temario_references,
    _similarity,
)
from app.db import SCHEMA


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test_dossier.db"
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    c.commit()
    yield c
    c.close()


def _insertar(conn, fuente, external_id, plaza, entidad, fecha_ini="", fecha_fin="", url_bases=""):
    conn.execute(
        """INSERT INTO anuncios
           (fuente, external_id, plaza, entidad, vacantes, url_bases,
            fecha_ini, fecha_fin, obs, content_hash, raw_data)
           VALUES (?, ?, ?, ?, '', ?, ?, ?, '', 'hash-de-prueba', '{}')""",
        (fuente, external_id, plaza, entidad, url_bases, fecha_ini, fecha_fin),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM anuncios WHERE fuente = ? AND external_id = ?",
        (fuente, external_id),
    ).fetchone()["id"]


@pytest.fixture
def datos(conn):
    """Cinco anuncios de prueba: dos variantes de 'auxiliar administrativo'
    (similares entre sí), dos variantes de 'técnico de sistemas' con orden de
    palabras distinto (similares entre sí), y un outlier sin relación con
    ninguno de los dos grupos."""
    ids = {}
    ids["admin_1"] = _insertar(
        conn, "diputacion", "d-1", "Auxiliar Administrativo",
        "Ayuntamiento de Benidorm", fecha_ini="2023-01-10", url_bases="https://ej.test/1",
    )
    ids["admin_2"] = _insertar(
        conn, "diputacion", "d-2", "Auxiliar Administrativo/a",
        "Diputación de Alicante", fecha_ini="2024-05-20", url_bases="https://ej.test/2",
    )
    ids["sistemas_1"] = _insertar(
        conn, "boe", "b-1", "Técnico de Sistemas de Información",
        "Diputación de Alicante", fecha_ini="2021-03-01", url_bases="https://ej.test/3",
    )
    ids["sistemas_2"] = _insertar(
        conn, "boe", "b-2", "Técnico en Sistemas de Información y Comunicaciones",
        "Ayuntamiento de Benidorm", fecha_ini="2020-11-15", url_bases="https://ej.test/4",
    )
    ids["outlier"] = _insertar(
        conn, "dogv", "g-1", "Ingeniero de Telecomunicaciones",
        "Ayuntamiento de Alicante", fecha_ini="2022-06-01", url_bases="https://ej.test/5",
    )
    return ids


# --- find_similar_processes -------------------------------------------------


def test_encuentra_variante_similar_y_excluye_el_propio(conn, datos):
    anuncio_nuevo = {"id": datos["admin_1"], "plaza": "Auxiliar Administrativo",
                      "fuente": "diputacion", "external_id": "d-1"}
    resultado = find_similar_processes(conn, anuncio_nuevo)

    ids_resultado = {r["entidad"] for r in resultado}
    assert "Diputación de Alicante" in ids_resultado  # admin_2, la variante similar
    assert all(r["plaza"] != "Auxiliar Administrativo" or r["entidad"] != "Ayuntamiento de Benidorm"
               for r in resultado)  # el propio admin_1 no debe aparecer


def test_no_encuentra_similitud_con_plaza_sin_relacion(conn, datos):
    anuncio_nuevo = {"id": datos["admin_1"], "plaza": "Auxiliar Administrativo"}
    resultado = find_similar_processes(conn, anuncio_nuevo)
    entidades = {r["entidad"] for r in resultado}
    assert "Ayuntamiento de Alicante" not in entidades  # outlier, sin relación


def test_similitud_tolera_orden_de_palabras_distinto(conn, datos):
    """'Técnico de Sistemas de Información' vs 'Técnico en Sistemas de
    Información y Comunicaciones' comparten casi todos los tokens aunque el
    orden y alguna palabra cambien; deben salir como similares."""
    anuncio_nuevo = {"id": datos["sistemas_1"], "plaza": "Técnico de Sistemas de Información"}
    resultado = find_similar_processes(conn, anuncio_nuevo)
    entidades = {r["entidad"] for r in resultado}
    assert "Ayuntamiento de Benidorm" in entidades  # sistemas_2


def test_resultado_ordenado_descendente_por_similitud(conn, datos):
    anuncio_nuevo = {"id": datos["admin_1"], "plaza": "Auxiliar Administrativo"}
    resultado = find_similar_processes(conn, anuncio_nuevo, limit=10)
    similitudes = [r["similitud"] for r in resultado]
    assert similitudes == sorted(similitudes, reverse=True)


def test_respeta_limit(conn, datos):
    # Insertamos más variantes de "administrativo" para tener de sobra.
    _insertar(conn, "diputacion", "d-3", "Administrativo/a", "Ayuntamiento de Alicante")
    _insertar(conn, "diputacion", "d-4", "Auxiliar Administrativo Interino", "Diputación de Alicante")
    anuncio_nuevo = {"id": datos["admin_1"], "plaza": "Auxiliar Administrativo"}
    resultado = find_similar_processes(conn, anuncio_nuevo, limit=2)
    assert len(resultado) <= 2


def test_excluye_por_fuente_y_external_id_si_no_hay_id(conn, datos):
    """Si el dict del anuncio no trae 'id' (p.ej. viene de un AnuncioRaw aún
    sin persistir), se debe poder excluir el propio registro por
    fuente+external_id en su lugar."""
    anuncio_nuevo = {"plaza": "Auxiliar Administrativo", "fuente": "diputacion", "external_id": "d-1"}
    resultado = find_similar_processes(conn, anuncio_nuevo)
    assert all(not (r["plaza"] == "Auxiliar Administrativo" and r["entidad"] == "Ayuntamiento de Benidorm")
               for r in resultado)


def test_plaza_vacia_devuelve_lista_vacia(conn, datos):
    assert find_similar_processes(conn, {"plaza": ""}) == []
    assert find_similar_processes(conn, {}) == []


def test_campos_devueltos(conn, datos):
    anuncio_nuevo = {"id": datos["admin_1"], "plaza": "Auxiliar Administrativo"}
    resultado = find_similar_processes(conn, anuncio_nuevo)
    assert resultado, "se esperaba al menos un proceso similar en los datos de prueba"
    primero = resultado[0]
    assert set(primero.keys()) == {"plaza", "entidad", "fecha", "url_bases", "similitud"}
    assert isinstance(primero["similitud"], float)


def test_similarity_umbral_documentado():
    """Dos plazas de categorías distintas deben quedar por debajo del umbral
    documentado (SIMILARITY_THRESHOLD = 0.35)."""
    from app.dossier import SIMILARITY_THRESHOLD
    assert _similarity("Auxiliar Administrativo", "Ingeniero de Telecomunicaciones") < SIMILARITY_THRESHOLD
    assert _similarity("Auxiliar Administrativo", "Auxiliar Administrativo/a") >= SIMILARITY_THRESHOLD


# --- temario_references ------------------------------------------------------


@pytest.fixture(autouse=False)
def _todas_las_urls_ok(monkeypatch):
    """Evita red real en los tests: toda URL se considera accesible (200)."""
    monkeypatch.setattr("app.dossier._url_ok", lambda url, timeout=None: True)


def test_categoria_administrativo(_todas_las_urls_ok):
    refs = temario_references("Auxiliar Administrativo")
    titulos = [r["titulo"] for r in refs]
    assert any("Estatuto Básico del Empleado Público" in t for t in titulos)
    assert any("39/2015" in t for t in titulos)
    assert any("40/2015" in t for t in titulos)
    assert any("Régimen Local" in t for t in titulos)
    assert len(refs) == 4  # solo la normativa base, sin extras


def test_categoria_informatico_anade_ens_sobre_la_base(_todas_las_urls_ok):
    refs = temario_references("Técnico Informático de Sistemas")
    titulos = [r["titulo"] for r in refs]
    assert any("Esquema Nacional de Seguridad" in t for t in titulos)
    assert any("Estatuto Básico del Empleado Público" in t for t in titulos)  # base incluida
    # Ley 39/2015 aparece una sola vez aunque la reclamen tanto la base como
    # la categoría informática (dedup por URL).
    assert sum("39/2015" in t for t in titulos) == 1


def test_categoria_docente_anade_lomloe(_todas_las_urls_ok):
    refs = temario_references("Profesor de Secundaria - Tecnología")
    titulos = [r["titulo"] for r in refs]
    assert any("LOMLOE" in t for t in titulos)
    assert any("Estatuto Básico del Empleado Público" in t for t in titulos)


def test_categoria_no_reconocida_devuelve_vacio(_todas_las_urls_ok):
    assert temario_references("Bombero/a") == []
    assert temario_references("") == []


def test_estructura_de_cada_referencia(_todas_las_urls_ok):
    refs = temario_references("Auxiliar Administrativo")
    assert refs, "se esperaban referencias para la categoría administrativo"
    for ref in refs:
        assert set(ref.keys()) == {"titulo", "url"}
        assert isinstance(ref["titulo"], str) and ref["titulo"]
        assert ref["url"].startswith("https://www.boe.es/")


def test_url_que_falla_la_comprobacion_en_caliente_se_descarta(monkeypatch):
    """Si `_url_ok` dice que una URL concreta no responde 200, esa referencia
    no debe aparecer en el resultado, aunque las demás de su categoría sí."""
    from app.dossier import _ENS

    def fake_url_ok(url, timeout=None):
        return url != _ENS["url"]

    monkeypatch.setattr("app.dossier._url_ok", fake_url_ok)
    refs = temario_references("Técnico Informático de Sistemas")
    urls = [r["url"] for r in refs]
    assert _ENS["url"] not in urls
    assert len(refs) == 4  # la base entera sigue presente, solo cae el ENS


# --- build_dossier ------------------------------------------------------------


def test_build_dossier_combina_ambas_partes(conn, datos, _todas_las_urls_ok):
    anuncio_nuevo = {"id": datos["admin_1"], "plaza": "Auxiliar Administrativo",
                      "entidad": "Ayuntamiento de Benidorm"}
    dossier = build_dossier(conn, anuncio_nuevo)
    assert set(dossier.keys()) == {"procesos_similares", "temario_referencias", "nota"}
    assert isinstance(dossier["procesos_similares"], list)
    assert isinstance(dossier["temario_referencias"], list)
    assert "OpoRadar" in dossier["nota"]
    assert dossier["temario_referencias"]  # administrativo detectado
