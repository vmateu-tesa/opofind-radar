"""Tests offline de app.notifier_telegram. Sin red real: todo en DRY_RUN o con
`requests.post` sustituido por un doble de prueba."""

import logging

import pytest

from app import notifier_telegram as nt


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch):
    """Por defecto cada test arranca en DRY_RUN y sin credenciales, como pide
    el encargo ('que send_message() no lanza excepción aunque
    TELEGRAM_BOT_TOKEN esté vacío'). Los tests que necesiten otra cosa la
    fijan explícitamente."""
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


def _post_que_falla_si_se_llama(*args, **kwargs):
    raise AssertionError("requests.post no debería llamarse en DRY_RUN")


ANUNCIO_COMPLETO = {
    "plaza": "Técnico de Sistemas de Información",
    "entidad": "Diputación de Alicante",
    "vacantes": "2",
    "url_bases": "https://sede.diputacionalicante.es/bases/11357.pdf",
    "fecha_ini": "2026-07-01",
    "fecha_fin": "2026-07-20",
    "obs": "Publicado en BOP nº 120 de 01/07/2026. Publicado en BOE de 05/07/2026.",
}


# ---------------------------------------------------------------------------
# format_nuevo
# ---------------------------------------------------------------------------

def test_format_nuevo_incluye_cabecera_y_campos():
    texto = nt.format_nuevo(ANUNCIO_COMPLETO, "telecomunicaciones_tic")

    assert "🚨" in texto
    assert "NUEVA CONVOCATORIA" in texto
    assert "Técnico de Sistemas de Información" in texto
    assert "Diputación de Alicante" in texto
    assert "2" in texto
    assert "2026-07-01" in texto
    assert "2026-07-20" in texto
    assert "https://sede.diputacionalicante.es/bases/11357.pdf" in texto
    assert "telecomunicaciones_tic" in texto


def test_format_nuevo_con_campos_vacios_no_lanza():
    anuncio_minimo = {"plaza": "", "entidad": "", "vacantes": "", "url_bases": ""}
    texto = nt.format_nuevo(anuncio_minimo, "perfil_x")
    assert "NUEVA CONVOCATORIA" in texto
    assert "(sin especificar)" in texto
    assert "(sin enlace disponible)" in texto


def test_format_nuevo_escapa_html_en_campos():
    anuncio = dict(ANUNCIO_COMPLETO)
    anuncio["plaza"] = "Técnico A&B <Sistemas>"
    texto = nt.format_nuevo(anuncio, "perfil_x")

    assert "A&amp;B &lt;Sistemas&gt;" in texto
    # No debe colarse el texto sin escapar (rompería el parse_mode HTML).
    assert "A&B <Sistemas>" not in texto


def test_format_nuevo_usa_negritas_html():
    texto = nt.format_nuevo(ANUNCIO_COMPLETO, "perfil_x")
    assert "<b>Plaza:</b>" in texto
    assert "<b>Entidad:</b>" in texto
    assert "<b>Vacantes:</b>" in texto


# ---------------------------------------------------------------------------
# format_actualizado
# ---------------------------------------------------------------------------

def test_format_actualizado_incluye_cabecera_y_diff():
    obs_anterior = "Publicado en BOP nº 120 de 01/07/2026."
    anuncio = dict(ANUNCIO_COMPLETO)
    anuncio["obs"] = "Publicado en BOP nº 120 de 01/07/2026. Publicado en BOE de 05/07/2026."

    texto = nt.format_actualizado(anuncio, "telecomunicaciones_tic", obs_anterior)

    assert "🔄" in texto
    assert "ACTUALIZACIÓN" in texto
    # obs_diff_suffix recorta la puntuación final del texto añadido.
    assert "Publicado en BOE de 05/07/2026" in texto
    # El texto que ya conocíamos no debe repetirse como "novedad".
    assert "Publicado en BOP nº 120" not in texto.split("Novedad en Obs:")[1]


def test_format_actualizado_sin_prefijo_comun_muestra_obs_completo():
    obs_anterior = "Texto original distinto."
    anuncio = dict(ANUNCIO_COMPLETO)
    anuncio["obs"] = "Texto completamente reescrito."

    texto = nt.format_actualizado(anuncio, "perfil_x", obs_anterior)

    assert "contenido modificado" in texto
    assert "Texto completamente reescrito." in texto


def test_format_actualizado_escapa_html():
    obs_anterior = ""
    anuncio = dict(ANUNCIO_COMPLETO)
    anuncio["obs"] = "Nuevo aviso <urgente> & importante"

    texto = nt.format_actualizado(anuncio, "perfil_x", obs_anterior)
    assert "&lt;urgente&gt;" in texto
    assert "&amp;" in texto


# ---------------------------------------------------------------------------
# send_message en DRY_RUN
# ---------------------------------------------------------------------------

def test_send_message_dry_run_no_llama_a_requests(monkeypatch):
    monkeypatch.setattr(nt.requests, "post", _post_que_falla_si_se_llama)
    resultado = nt.send_message("Hola mundo")
    assert resultado is True


def test_send_message_dry_run_sin_token_no_lanza_excepcion(monkeypatch):
    # TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID ya están ausentes por el fixture.
    monkeypatch.setattr(nt.requests, "post", _post_que_falla_si_se_llama)
    resultado = nt.send_message("Mensaje de prueba sin credenciales")
    assert resultado is True


def test_send_message_dry_run_loguea_texto_completo(monkeypatch, caplog):
    monkeypatch.setattr(nt.requests, "post", _post_que_falla_si_se_llama)
    texto_largo = "X" * 5000
    with caplog.at_level(logging.INFO):
        resultado = nt.send_message(texto_largo)

    assert resultado is True
    mensajes = " ".join(r.getMessage() for r in caplog.records)
    assert "[DRY_RUN]" in mensajes
    assert texto_largo in mensajes


# ---------------------------------------------------------------------------
# _split_message
# ---------------------------------------------------------------------------

def test_split_message_por_debajo_del_limite_no_trocea():
    texto = "línea corta"
    assert nt._split_message(texto) == [texto]


def test_split_message_por_encima_del_limite_trocea():
    texto = "\n".join(f"línea número {i} con algo de relleno" for i in range(400))
    assert len(texto) > nt.MAX_MESSAGE_LENGTH

    fragmentos = nt._split_message(texto)

    assert len(fragmentos) > 1
    for frag in fragmentos:
        assert len(frag) <= nt.MAX_MESSAGE_LENGTH
    # No se pierde contenido al trocear.
    assert "\n".join(fragmentos) == texto or "".join(fragmentos).replace("\n", "") == texto.replace("\n", "")


def test_split_message_corta_en_salto_de_linea_no_a_mitad_de_palabra():
    lineas = [f"aviso {i}: " + ("z" * 50) for i in range(150)]
    texto = "\n".join(lineas)

    fragmentos = nt._split_message(texto)

    assert len(fragmentos) > 1
    # Cada fragmento debe reconstruirse con líneas completas del original.
    reconstruido = []
    for frag in fragmentos:
        reconstruido.extend(frag.split("\n"))
    assert reconstruido == lineas


# ---------------------------------------------------------------------------
# send_message fuera de DRY_RUN (con requests.post simulado, sigue sin red real)
# ---------------------------------------------------------------------------

class _RespuestaFalsa:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text or str(json_data)

    def json(self):
        return self._json_data


def test_send_message_no_dry_run_sin_credenciales_devuelve_false(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setattr(nt.requests, "post", _post_que_falla_si_se_llama)

    resultado = nt.send_message("Hola")
    assert resultado is False


def test_send_message_no_dry_run_envia_correctamente(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-de-prueba")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    llamadas = []

    def post_falso(url, json, timeout):
        llamadas.append((url, json, timeout))
        return _RespuestaFalsa(200)

    monkeypatch.setattr(nt.requests, "post", post_falso)

    resultado = nt.send_message("Mensaje corto")

    assert resultado is True
    assert len(llamadas) == 1
    url, payload, _ = llamadas[0]
    assert "token-de-prueba" in url
    assert payload["chat_id"] == "12345"
    assert payload["parse_mode"] == "HTML"


def test_send_message_no_dry_run_trocea_mensajes_largos(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-de-prueba")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    llamadas = []

    def post_falso(url, json, timeout):
        llamadas.append(json["text"])
        return _RespuestaFalsa(200)

    monkeypatch.setattr(nt.requests, "post", post_falso)

    texto_largo = "\n".join(f"línea {i}" for i in range(1000))
    resultado = nt.send_message(texto_largo)

    assert resultado is True
    assert len(llamadas) > 1
    for fragmento in llamadas:
        assert len(fragmento) <= nt.MAX_MESSAGE_LENGTH


def test_send_message_reintenta_una_vez_ante_429_y_luego_ok(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-de-prueba")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(nt.time, "sleep", lambda segundos: None)

    respuestas = [
        _RespuestaFalsa(429, json_data={"parameters": {"retry_after": 2}}),
        _RespuestaFalsa(200),
    ]
    llamadas = []

    def post_falso(url, json, timeout):
        llamadas.append(json)
        return respuestas.pop(0)

    monkeypatch.setattr(nt.requests, "post", post_falso)

    resultado = nt.send_message("Mensaje que topa con rate limit")

    assert resultado is True
    assert len(llamadas) == 2


def test_send_message_no_reintenta_mas_de_una_vez_ante_429_persistente(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-de-prueba")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(nt.time, "sleep", lambda segundos: None)

    llamadas = []

    def post_falso(url, json, timeout):
        llamadas.append(json)
        return _RespuestaFalsa(429, json_data={"parameters": {"retry_after": 1}})

    monkeypatch.setattr(nt.requests, "post", post_falso)

    resultado = nt.send_message("Mensaje que topa con rate limit persistente")

    assert resultado is False
    assert len(llamadas) == 2  # intento inicial + 1 reintento, no más


def test_send_message_error_de_red_no_lanza_excepcion(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token-de-prueba")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "12345")

    def post_que_lanza(url, json, timeout):
        raise nt.requests.RequestException("fallo de red simulado")

    monkeypatch.setattr(nt.requests, "post", post_que_lanza)

    resultado = nt.send_message("Mensaje")
    assert resultado is False
