"""Tests de integracion del motor de avisos de plazo cableado en main.py:
revisar_plazos() y el endpoint /api/estado."""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main as main_module
from core.matcher import Matcher
from db.models import Base, Convocatoria, AvisoPlazo


@pytest.fixture
def SessionLocal(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    Base.metadata.create_all(bind=engine)
    SL = sessionmaker(bind=engine)
    monkeypatch.setattr(main_module, "get_session", lambda: SL())
    return SL


class _Grabador:
    def __init__(self):
        self.mensajes = []

    def send_message(self, texto):
        self.mensajes.append(texto)
        return True


def _conv(**kw):
    base = dict(id="c1", fuente="test", titulo="Ingeniero de Telecomunicaciones",
               entidad="Ayuntamiento de Elche", hash_contenido="h", tipo="convocatoria",
               seguimiento=True, fecha_inicio="17/06/2026", fecha_fin="01/07/2026")
    base.update(kw)
    return Convocatoria(**base)


def test_aviso_apertura_una_sola_vez(SessionLocal):
    s = SessionLocal()
    s.add(_conv())
    s.commit(); s.close()

    grab = _Grabador()
    s = SessionLocal()
    # hoy = primer dia del plazo -> aviso de apertura
    main_module.revisar_plazos(s, Matcher(), [("telegram", grab)], hoy=date(2026, 6, 17))
    s.close()
    assert len(grab.mensajes) == 1
    assert "PLAZO ABIERTO" in grab.mensajes[0]

    # Segundo ciclo el mismo dia: NO se repite (persistido en AvisoPlazo).
    s = SessionLocal()
    main_module.revisar_plazos(s, Matcher(), [("telegram", grab)], hoy=date(2026, 6, 17))
    s.close()
    assert len(grab.mensajes) == 1


def test_aviso_cierre_ultimo_dia(SessionLocal):
    s = SessionLocal()
    c = _conv()
    s.add(c)
    # marcamos apertura ya enviada para aislar el aviso de cierre
    s.add(AvisoPlazo(convocatoria_id="c1", tipo_aviso="apertura"))
    s.commit(); s.close()

    grab = _Grabador()
    s = SessionLocal()
    main_module.revisar_plazos(s, Matcher(), [("email", grab)], hoy=date(2026, 7, 1))
    s.close()
    assert len(grab.mensajes) == 1
    assert "ULTIMO DIA" in grab.mensajes[0] or "CIERRA" in grab.mensajes[0]


def test_sin_canales_no_marca_para_no_perderlos(SessionLocal):
    """Sin canales configurados, los avisos NO se marcan como enviados: asi
    cuando el usuario configure un canal, los recibira."""
    s = SessionLocal()
    s.add(_conv())
    s.commit(); s.close()

    s = SessionLocal()
    main_module.revisar_plazos(s, Matcher(), [], hoy=date(2026, 6, 17))
    n = s.query(AvisoPlazo).count()
    s.close()
    assert n == 0  # nada registrado

    # Al configurar un canal, ahora si llega.
    grab = _Grabador()
    s = SessionLocal()
    main_module.revisar_plazos(s, Matcher(), [("telegram", grab)], hoy=date(2026, 6, 17))
    s.close()
    assert len(grab.mensajes) == 1


def test_agrupa_si_hay_muchos_avisos(SessionLocal):
    s = SessionLocal()
    for i in range(7):
        s.add(_conv(id=f"c{i}", titulo=f"Ingeniero Informatico {i}"))
    s.commit(); s.close()

    grab = _Grabador()
    s = SessionLocal()
    # 7 convocatorias abiertas -> 7 aperturas > 5 -> un solo mensaje resumen
    main_module.revisar_plazos(s, Matcher(), [("telegram", grab)], hoy=date(2026, 6, 17))
    s.close()
    assert len(grab.mensajes) == 1
    assert grab.mensajes[0].count("•") == 7


def test_endpoint_estado_forma_y_sin_secretos(SessionLocal, monkeypatch):
    monkeypatch.setenv("ENABLE_TELEGRAM", "0")
    monkeypatch.setenv("ENABLE_WHATSAPP", "0")
    monkeypatch.setenv("ENABLE_EMAIL", "0")

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[main_module.get_db] = override_db
    client = TestClient(main_module.app)
    r = client.get("/api/estado")
    main_module.app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert set(data["canales"].keys()) == {"telegram", "whatsapp", "email"}
    assert data["canales"] == {"telegram": False, "whatsapp": False, "email": False}
    assert "total_convocatorias" in data and "seguidas" in data
    # ningun valor de secreto en la respuesta
    assert "TOKEN" not in r.text and "PASSWORD" not in r.text
