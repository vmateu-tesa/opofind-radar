"""Tests de las vigilancias dirigidas: reglas de deteccion
(config/vigilancias.py), sincronizacion a la tabla y aviso prioritario
cuando la plaza vigilada aparece en una convocatoria."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main as main_module
from config import vigilancias as vig_cfg
from db.models import Base, Convocatoria, Vigilancia
from scrapers.base import ConvocatoriaData


VIG_BENIDORM = vig_cfg.por_slug("benidorm-ing-tecnico-telecomunicacion")


# ---------------------------------------------------------------------------
# coincide(): reglas de la vigilancia de Benidorm
# ---------------------------------------------------------------------------

def test_coincide_telecom_en_benidorm():
    assert vig_cfg.coincide(VIG_BENIDORM,
                            "Bolsa de Ingeniero/a Técnico/a de Telecomunicación",
                            "Ayuntamiento de Benidorm", "", "Benidorm") is True


def test_coincide_por_codigo_de_puesto():
    assert vig_cfg.coincide(VIG_BENIDORM,
                            "Provisión puesto 1.11.139",
                            "Ayuntamiento de Benidorm", "", "Benidorm") is True


def test_no_coincide_otra_plaza_en_benidorm():
    assert vig_cfg.coincide(VIG_BENIDORM,
                            "Ingeniero/a Informático/a",
                            "Ayuntamiento de Benidorm", "", "Benidorm") is False


def test_no_coincide_telecom_en_otro_municipio():
    # La restriccion de municipio evita avisar por telecomunicaciones de otro sitio.
    assert vig_cfg.coincide(VIG_BENIDORM,
                            "Ingeniero de Telecomunicación",
                            "Ayuntamiento de Alicante", "", "Alicante") is False


# ---------------------------------------------------------------------------
# Sincronizacion + deteccion con aviso (patron de fakes de test_seguimiento)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_session_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "test_vigilancias.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr(main_module, "get_session", lambda: SessionLocal())
    return SessionLocal


class _RecordingNotifier:
    def __init__(self):
        self.mensajes = []

    def send_message(self, texto):
        self.mensajes.append(texto)
        return True


def test_sincronizar_es_idempotente(temp_session_factory):
    session = temp_session_factory()
    main_module.sincronizar_vigilancias(session)
    main_module.sincronizar_vigilancias(session)
    assert session.query(Vigilancia).count() == len(vig_cfg.VIGILANCIAS)
    v = session.query(Vigilancia).filter_by(slug=VIG_BENIDORM["slug"]).first()
    assert v.estado == "vigilando"
    session.close()


def test_revisar_detecta_y_avisa(temp_session_factory):
    session = temp_session_factory()
    main_module.sincronizar_vigilancias(session)
    # Aparece la convocatoria vigilada.
    session.add(Convocatoria(
        id="benidorm-telecom-1", fuente="benidorm",
        titulo="Bolsa de Ingeniero/a Técnico/a de Telecomunicación",
        entidad="Ayuntamiento de Benidorm", enlace="https://benidorm.test/tel.pdf",
        hash_contenido="x", fecha_inicio="", fecha_fin="", seguimiento=False,
    ))
    session.commit()

    notifier = _RecordingNotifier()
    main_module.revisar_vigilancias(session, [("telegram", notifier)])

    v = session.query(Vigilancia).filter_by(slug=VIG_BENIDORM["slug"]).first()
    assert v.estado == "detectada"
    assert v.convocatoria_id == "benidorm-telecom-1"
    conv = session.query(Convocatoria).filter_by(id="benidorm-telecom-1").first()
    assert conv.seguimiento is True  # queda seguida
    assert len(notifier.mensajes) == 1
    assert "PLAZA VIGILADA" in notifier.mensajes[0]
    session.close()


def test_no_reavisa_si_ya_detectada(temp_session_factory):
    session = temp_session_factory()
    main_module.sincronizar_vigilancias(session)
    session.add(Convocatoria(
        id="benidorm-telecom-1", fuente="benidorm",
        titulo="Ingeniero Técnico de Telecomunicación",
        entidad="Ayuntamiento de Benidorm", enlace="", hash_contenido="x",
        fecha_inicio="", fecha_fin="",
    ))
    session.commit()

    notifier = _RecordingNotifier()
    main_module.revisar_vigilancias(session, [("telegram", notifier)])
    assert len(notifier.mensajes) == 1
    # Segunda pasada: ya esta 'detectada', no debe volver a avisar.
    main_module.revisar_vigilancias(session, [("telegram", notifier)])
    assert len(notifier.mensajes) == 1
    session.close()


def test_no_detecta_sin_convocatoria_que_encaje(temp_session_factory):
    session = temp_session_factory()
    main_module.sincronizar_vigilancias(session)
    session.add(Convocatoria(
        id="benidorm-otra", fuente="benidorm", titulo="Peón de Jardinería",
        entidad="Ayuntamiento de Benidorm", enlace="", hash_contenido="x",
        fecha_inicio="", fecha_fin="",
    ))
    session.commit()

    notifier = _RecordingNotifier()
    main_module.revisar_vigilancias(session, [("telegram", notifier)])

    v = session.query(Vigilancia).filter_by(slug=VIG_BENIDORM["slug"]).first()
    assert v.estado == "vigilando"
    assert notifier.mensajes == []
    session.close()
