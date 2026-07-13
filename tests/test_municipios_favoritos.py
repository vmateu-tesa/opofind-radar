"""Tests de la funcionalidad de municipios favoritos: deteccion del
municipio canonico (core/geo.py), endpoints CRUD y notificacion cuando una
oferta de un municipio favorito aparece o cambia, aunque no matchee ningun
perfil de alertas.yaml ni este en seguimiento manual."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main as main_module
from core import geo
from db.models import Base, Convocatoria, MunicipioFavorito
from scrapers.base import ConvocatoriaData


# ---------------------------------------------------------------------------
# core/geo.py: municipio_de / resolver_municipio / lista_municipios
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("entidad,esperado", [
    ("Ayuntamiento de Elche", "Elche"),
    ("Ajuntament d'Elx", "Elche"),
    ("Ayto. de la Vila Joiosa", "Villajoyosa"),
    ("AYUNTAMIENTO DE VILLAJOYOSA", "Villajoyosa"),
    ("Ajuntament de l'Alfàs del Pi", "L'Alfàs del Pi"),
    ("Ayuntamiento de Alicante", "Alicante"),
    ("Ayuntamiento de Muro de Alcoy", "Muro de Alcoy"),   # no debe caer en "Alcoy"
    ("Ajuntament de Sant Joan d'Alacant", "Sant Joan d'Alacant"),  # no "Alicante"
    ("Ayuntamiento de Callosa de Segura", "Callosa de Segura"),
    ("Ayuntamiento de Madrid", None),
])
def test_municipio_de_entidad(entidad, esperado):
    assert geo.municipio_de(entidad) == esperado


def test_municipio_de_diputacion_no_es_alicante():
    # La Diputacion es provincial: sin municipio en el titulo -> None.
    assert geo.municipio_de("EXCMA. DIPUTACIÓN PROVINCIAL DE ALICANTE") is None
    assert geo.municipio_de("Diputación de Alicante") is None
    # Pero si el titulo menciona un municipio concreto, se usa.
    assert geo.municipio_de("Diputación de Alicante", "Bolsa de auxiliar en Elda") == "Elda"


def test_municipio_de_mira_titulo_si_entidad_no_dice_nada():
    assert geo.municipio_de("ADMINISTRACION LOCAL",
                            "Resolución del Ayuntamiento de Santa Pola sobre bolsa") == "Santa Pola"


def test_municipio_de_vacio():
    assert geo.municipio_de("", "") is None
    assert geo.municipio_de(None, None) is None


@pytest.mark.parametrize("nombre,esperado", [
    ("elx", "Elche"),
    ("ELCHE", "Elche"),
    ("Villajoyosa", "Villajoyosa"),
    ("la vila joiosa", "Villajoyosa"),
    ("dénia", "Dénia"),
    ("denia", "Dénia"),
    ("Madrid", None),
    ("", None),
    (None, None),
])
def test_resolver_municipio(nombre, esperado):
    assert geo.resolver_municipio(nombre) == esperado


def test_lista_municipios_completa_y_ordenada():
    ms = geo.lista_municipios()
    assert len(ms) == len(geo.MUNICIPIOS_CANONICOS)
    assert "Elche" in ms and "Villajoyosa" in ms and "Torrevieja" in ms
    normalizados = [geo._norm(m) for m in ms]
    assert normalizados == sorted(normalizados)


def test_es_alicante_sigue_funcionando_tras_el_refactor():
    # Garantia de no-regresion del filtro original sobre el nuevo dict.
    assert geo.es_alicante("Ajuntament de la Vila Joiosa") is True
    assert geo.es_alicante("Ayuntamiento de Valencia") is False


# ---------------------------------------------------------------------------
# Endpoints (llamados directamente con una Session; sin TestClient porque
# httpx no esta en requirements)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_session_factory(tmp_path, monkeypatch):
    db_path = tmp_path / "test_favoritos.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    monkeypatch.setattr(main_module, "get_session", lambda: SessionLocal())
    return SessionLocal


def test_crud_municipios_favoritos(temp_session_factory):
    session = temp_session_factory()

    # Alta resolviendo variante -> canonico.
    res = main_module.add_municipio_favorito(main_module.MunicipioIn(nombre="elx"), db=session)
    assert res["nombre"] == "Elche"

    # Idempotente: repetir devuelve el mismo, sin duplicar.
    res2 = main_module.add_municipio_favorito(main_module.MunicipioIn(nombre="Elche"), db=session)
    assert res2["id"] == res["id"]
    assert session.query(MunicipioFavorito).count() == 1

    # Nombre invalido -> 400.
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        main_module.add_municipio_favorito(main_module.MunicipioIn(nombre="Madrid"), db=session)
    assert exc.value.status_code == 400

    # Listado.
    lista = main_module.read_municipios_favoritos(db=session)
    assert [m["nombre"] for m in lista] == ["Elche"]

    # /api/municipios refleja el favorito.
    municipios = main_module.read_municipios(db=session)
    elche = next(m for m in municipios if m["nombre"] == "Elche")
    assert elche["favorito"] is True
    denia = next(m for m in municipios if m["nombre"] == "Dénia")
    assert denia["favorito"] is False

    # Borrado (tambien resuelve variantes) y 404 si no estaba.
    res3 = main_module.del_municipio_favorito("elx", db=session)
    assert res3 == {"ok": True, "nombre": "Elche"}
    with pytest.raises(HTTPException) as exc:
        main_module.del_municipio_favorito("Elche", db=session)
    assert exc.value.status_code == 404
    session.close()


def test_estado_incluye_contador_de_favoritos(temp_session_factory, monkeypatch):
    session = temp_session_factory()
    session.add(MunicipioFavorito(nombre="Elche"))
    session.commit()
    res = main_module.estado(db=session)
    assert res["municipios_favoritos"] == 1
    session.close()


def test_read_convocatorias_incluye_campos_calculados(temp_session_factory):
    session = temp_session_factory()
    session.add(Convocatoria(
        id="fav-test-1", fuente="test", titulo="Bolsa de administrativo",
        entidad="Ayuntamiento de Elche", enlace="https://ejemplo.test/1.pdf",
        hash_contenido="x", fecha_inicio="", fecha_fin="",
    ))
    session.commit()
    filas = main_module.read_convocatorias(db=session)
    assert len(filas) == 1
    fila = filas[0]
    assert fila["plazo_estado"] == "sin_fechas"
    assert fila["dias_restantes"] is None
    assert fila["municipio"] == "Elche"
    session.close()


# ---------------------------------------------------------------------------
# Notificacion: oferta de municipio favorito avisa aunque no matchee perfil
# (mismo patron de fakes que tests/test_seguimiento.py)
# ---------------------------------------------------------------------------

class _FakeScraperElche:
    """Plaza en Elche cuyo texto no matchea ningun perfil de alertas.yaml."""

    def scrape(self):
        return [
            ConvocatoriaData(
                id_origen="fav-elche-1",
                fuente="test",
                titulo="Médico de familia",  # excluido por los perfiles reales
                entidad="Ayuntamiento de Elche",
                enlace="https://ejemplo.test/elche.pdf",
                fecha_inicio="",
                fecha_fin="",
                observaciones="",
                vacantes="1",
            )
        ]


class _FakeScraperVacio:
    def __init__(self, *args, **kwargs):
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
    for nombre in ("DipBolsaOfertaScraper", "BoeScraper", "BenidormScraper",
                   "DogvScraper", "BopAlicanteScraper", "ElcheScraper",
                   "GestionaScraper", "AlfazScraper", "VillajoyosaScraper"):
        monkeypatch.setattr(main_module, nombre, _FakeScraperVacio)


def test_oferta_de_municipio_favorito_notifica(temp_session_factory, monkeypatch):
    monkeypatch.setenv("ENABLE_TELEGRAM", "1")
    monkeypatch.setenv("ENABLE_WHATSAPP", "0")
    telegram = _RecordingNotifier()
    monkeypatch.setattr(main_module, "TelegramNotifier", lambda: telegram)
    monkeypatch.setattr(main_module, "WhatsappNotifier", lambda: _RecordingNotifier())
    _patch_scrapers(monkeypatch, _FakeScraperElche())

    session = temp_session_factory()
    session.add(MunicipioFavorito(nombre="Elche"))
    session.commit()
    session.close()

    main_module.check_updates()

    assert len(telegram.mensajes) == 1
    assert "Municipio favorito" in telegram.mensajes[0]
    assert "Elche" in telegram.mensajes[0]


def test_oferta_sin_municipio_favorito_no_notifica(temp_session_factory, monkeypatch):
    monkeypatch.setenv("ENABLE_TELEGRAM", "1")
    monkeypatch.setenv("ENABLE_WHATSAPP", "0")
    telegram = _RecordingNotifier()
    monkeypatch.setattr(main_module, "TelegramNotifier", lambda: telegram)
    monkeypatch.setattr(main_module, "WhatsappNotifier", lambda: _RecordingNotifier())
    _patch_scrapers(monkeypatch, _FakeScraperElche())

    # Favorito de OTRO municipio: la oferta de Elche no debe avisar.
    session = temp_session_factory()
    session.add(MunicipioFavorito(nombre="Torrevieja"))
    session.commit()
    session.close()

    main_module.check_updates()

    assert telegram.mensajes == []
