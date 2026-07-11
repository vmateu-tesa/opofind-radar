"""Test: /api/generar-estudio y /api/generar-test deben rechazar
convocatorias que no sean tipo='convocatoria' (proceso selectivo abierto).
Generar temario/test para una lista de admitidos o un nombramiento no
tiene sentido y desperdicia cuota de Gemini."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main as main_module
from db.models import Base, Convocatoria


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test_generar.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    session = SessionLocal()
    session.add(Convocatoria(
        id="c-convocatoria", fuente="test", titulo="Tecnico Informatico",
        entidad="Ayto Prueba", hash_contenido="h1", tipo="convocatoria",
    ))
    session.add(Convocatoria(
        id="c-listas", fuente="test", titulo="Lista provisional admitidos",
        entidad="Ayto Prueba", hash_contenido="h2", tipo="listas",
    ))
    session.add(Convocatoria(
        id="c-nombramiento", fuente="test", titulo="Nombramiento funcionario de carrera",
        entidad="Ayto Prueba", hash_contenido="h3", tipo="nombramiento",
    ))
    session.commit()
    session.close()

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_get_db
    monkeypatch.setattr(main_module, "_last_call", {})  # sin rate limit entre tests
    yield TestClient(main_module.app)
    main_module.app.dependency_overrides.clear()


def test_convocatoria_real_permite_generar_estudio(client, monkeypatch):
    monkeypatch.setattr(
        main_module.StudyGenerator, "generate_syllabus", lambda self, texto: "Tema 1: ..."
    )
    resp = client.post("/api/generar-estudio/c-convocatoria")
    assert resp.status_code == 200
    assert "temario" in resp.json()


def test_listas_rechaza_generar_estudio(client):
    resp = client.post("/api/generar-estudio/c-listas")
    assert resp.status_code == 200  # el endpoint devuelve 200 con {"error": ...}, no 4xx
    data = resp.json()
    assert "error" in data
    assert "listas" in data["error"]


def test_nombramiento_rechaza_generar_test(client):
    resp = client.post("/api/generar-test/c-nombramiento")
    data = resp.json()
    assert "error" in data
    assert "nombramiento" in data["error"]


def test_listas_rechaza_generar_test(client):
    resp = client.post("/api/generar-test/c-listas")
    data = resp.json()
    assert "error" in data
