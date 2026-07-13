"""Test de integracion: una convocatoria marcada como 'seguimiento' debe
notificar ante cualquier actualizacion, aunque no matchee ningun perfil de
alertas.yaml (funcionalidad pedida explicitamente: marcar una convocatoria
de interes y que avise si sale info nueva -- listas, resultado, etc.)."""

import sqlite3

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main as main_module
from db.models import Base, Convocatoria
from scrapers.base import ConvocatoriaData


@pytest.fixture
def temp_session_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "test_seguimiento.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr(main_module, "get_session", lambda: SessionLocal())
    return SessionLocal


class _FakeScraperSinMatch:
    """Devuelve siempre la misma plaza, cuyo texto no coincide con ningun
    perfil real de config/alertas.yaml (nada de informatica/docencia/etc)."""

    def __init__(self, observaciones=""):
        self.observaciones = observaciones

    def scrape(self):
        return [
            ConvocatoriaData(
                id_origen="test-seguimiento-1",
                fuente="test",
                titulo="Médico de familia",  # excluido por Global_Provincia, no matchea nada
                entidad="Ayuntamiento de Prueba",
                enlace="https://ejemplo.test/1.pdf",
                fecha_inicio="",
                fecha_fin="",
                observaciones=self.observaciones,
                vacantes="1",
            )
        ]


class _FakeScraperVacio:
    def __init__(self, *args, **kwargs):
        # Acepta cualquier argumento (p.ej. BopAlicanteScraper(dias_atras=...)).
        pass

    def scrape(self):
        return []


class _RecordingNotifier:
    def __init__(self):
        self.mensajes = []

    def send_message(self, texto):
        self.mensajes.append(texto)
        return True


def _patch_scrapers(monkeypatch, principal):
    monkeypatch.setattr(main_module, "DipOtrasOposicionesScraper", lambda: principal)
    monkeypatch.setattr(main_module, "DipBolsaOfertaScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "BoeScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "BenidormScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "DogvScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "BopAlicanteScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "ElcheScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "GestionaScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "AlfazScraper", _FakeScraperVacio)
    monkeypatch.setattr(main_module, "VillajoyosaScraper", _FakeScraperVacio)


def test_convocatoria_sin_seguimiento_y_sin_match_no_notifica(temp_session_factory, monkeypatch):
    monkeypatch.setenv("ENABLE_TELEGRAM", "1")
    monkeypatch.setenv("ENABLE_WHATSAPP", "0")
    telegram = _RecordingNotifier()
    monkeypatch.setattr(main_module, "TelegramNotifier", lambda: telegram)
    monkeypatch.setattr(main_module, "WhatsappNotifier", lambda: _RecordingNotifier())
    _patch_scrapers(monkeypatch, _FakeScraperSinMatch())

    main_module.check_updates()

    assert telegram.mensajes == []


def test_convocatoria_seguida_notifica_al_actualizarse_sin_match(temp_session_factory, monkeypatch):
    monkeypatch.setenv("ENABLE_TELEGRAM", "1")
    monkeypatch.setenv("ENABLE_WHATSAPP", "0")
    telegram = _RecordingNotifier()
    monkeypatch.setattr(main_module, "TelegramNotifier", lambda: telegram)
    monkeypatch.setattr(main_module, "WhatsappNotifier", lambda: _RecordingNotifier())

    # Ciclo 1: crea la convocatoria (sin match, sin seguimiento -> sin aviso).
    _patch_scrapers(monkeypatch, _FakeScraperSinMatch(observaciones=""))
    main_module.check_updates()
    assert telegram.mensajes == []

    # El usuario la marca como seguida.
    session = temp_session_factory()
    conv = session.query(Convocatoria).filter_by(id="test-seguimiento-1").first()
    assert conv is not None
    assert conv.seguimiento is False
    conv.seguimiento = True
    session.commit()
    session.close()

    # Ciclo 2: la misma convocatoria cambia (nueva Obs) -> debe notificar,
    # aunque el texto siga sin matchear ningun perfil.
    _patch_scrapers(monkeypatch, _FakeScraperSinMatch(observaciones="Nueva publicacion BOP."))
    main_module.check_updates()

    assert len(telegram.mensajes) == 1
    assert "seguimiento manual" in telegram.mensajes[0] or "seguimiento" in telegram.mensajes[0].lower()

    session = temp_session_factory()
    conv = session.query(Convocatoria).filter_by(id="test-seguimiento-1").first()
    assert conv.estado == "actualizado"
    assert conv.seguimiento is True  # se mantiene tras la actualizacion
    session.close()


def test_tipo_se_asigna_al_crear(temp_session_factory, monkeypatch):
    monkeypatch.setenv("ENABLE_TELEGRAM", "0")
    monkeypatch.setenv("ENABLE_WHATSAPP", "0")
    monkeypatch.setattr(main_module, "TelegramNotifier", lambda: _RecordingNotifier())
    monkeypatch.setattr(main_module, "WhatsappNotifier", lambda: _RecordingNotifier())
    _patch_scrapers(monkeypatch, _FakeScraperSinMatch())

    main_module.check_updates()

    session = temp_session_factory()
    conv = session.query(Convocatoria).filter_by(id="test-seguimiento-1").first()
    assert conv.tipo == "convocatoria"
    session.close()
