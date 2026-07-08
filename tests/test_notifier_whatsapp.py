"""Tests del notificador secundario de WhatsApp (app/notifier_whatsapp.py).

Todos los tests son offline: en DRY_RUN no se llama a requests.post en
absoluto, y cuando se simula el modo real se sustituye requests.post por un
doble de prueba (monkeypatch) que nunca toca la red. En particular se cubre
el caso de fallback automático a plantilla cuando Meta responde que la
ventana de servicio de 24h está cerrada (error 131047).
"""

import requests

from app.notifier_whatsapp import format_actualizado, format_nuevo, send_message


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload


def _set_whatsapp_env(monkeypatch, dry_run: bool):
    monkeypatch.setenv("DRY_RUN", "true" if dry_run else "false")
    monkeypatch.setenv("WHATSAPP_TOKEN", "token-de-prueba")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "1234567890")
    monkeypatch.setenv("WHATSAPP_TO_NUMBER", "34600000000")
    monkeypatch.setenv("WHATSAPP_TEMPLATE_NAME", "opo_alerta")


def test_dry_run_no_llama_a_la_red(monkeypatch):
    """En DRY_RUN, send_message no debe invocar requests.post bajo ningún
    concepto: si lo hiciera, este test fallaría porque _post_no_debe_llamarse
    lanza una excepción."""
    _set_whatsapp_env(monkeypatch, dry_run=True)

    def _post_no_debe_llamarse(*args, **kwargs):
        raise AssertionError("requests.post no debe llamarse en DRY_RUN")

    monkeypatch.setattr(requests, "post", _post_no_debe_llamarse)

    assert send_message("Aviso de prueba") is True


def test_envio_texto_libre_exitoso(monkeypatch):
    """Modo real: si la API acepta el texto libre a la primera, no debe
    intentarse ningún fallback a plantilla."""
    _set_whatsapp_env(monkeypatch, dry_run=False)
    llamadas = []

    def fake_post(url, headers=None, json=None, timeout=None):
        llamadas.append(json)
        return FakeResponse(200, {"messages": [{"id": "wamid.abc"}]})

    monkeypatch.setattr(requests, "post", fake_post)

    assert send_message("Aviso de prueba") is True
    assert len(llamadas) == 1
    assert llamadas[0]["type"] == "text"
    assert llamadas[0]["text"]["body"] == "Aviso de prueba"


def test_fallback_a_plantilla_cuando_ventana_24h_cerrada(monkeypatch):
    """Si el texto libre falla con el código de re-engagement (131047),
    send_message debe reintentar automáticamente con type='template' usando
    el nombre configurado en WHATSAPP_TEMPLATE_NAME, y devolver True si esa
    segunda llamada tiene éxito."""
    _set_whatsapp_env(monkeypatch, dry_run=False)
    llamadas = []

    def fake_post(url, headers=None, json=None, timeout=None):
        llamadas.append(json)
        if json["type"] == "text":
            return FakeResponse(
                400,
                {
                    "error": {
                        "message": "Re-engagement message",
                        "code": 131047,
                        "error_subcode": 2494010,
                    }
                },
            )
        return FakeResponse(200, {"messages": [{"id": "wamid.def"}]})

    monkeypatch.setattr(requests, "post", fake_post)

    resultado = send_message("Nueva convocatoria disponible")

    assert resultado is True
    assert len(llamadas) == 2
    assert llamadas[0]["type"] == "text"
    assert llamadas[1]["type"] == "template"
    assert llamadas[1]["template"]["name"] == "opo_alerta"
    assert llamadas[1]["template"]["language"] == {"code": "es"}
    parametro = llamadas[1]["template"]["components"][0]["parameters"][0]
    assert parametro["text"] == "Nueva convocatoria disponible"


def test_fallo_no_recuperable_devuelve_false_sin_reintentar(monkeypatch):
    """Un error que no es de ventana de 24h cerrada (p.ej. token inválido) no
    debe disparar el fallback a plantilla: se registra el fallo y se
    devuelve False directamente."""
    _set_whatsapp_env(monkeypatch, dry_run=False)
    llamadas = []

    def fake_post(url, headers=None, json=None, timeout=None):
        llamadas.append(json)
        return FakeResponse(401, {"error": {"message": "Invalid OAuth access token", "code": 190}})

    monkeypatch.setattr(requests, "post", fake_post)

    assert send_message("Aviso de prueba") is False
    assert len(llamadas) == 1


def test_excepcion_de_red_devuelve_false(monkeypatch):
    """Un fallo de conexión (sin respuesta HTTP) no debe propagar la
    excepción: send_message debe capturarla y devolver False."""
    _set_whatsapp_env(monkeypatch, dry_run=False)

    def fake_post(*args, **kwargs):
        raise requests.ConnectionError("no hay red")

    monkeypatch.setattr(requests, "post", fake_post)

    assert send_message("Aviso de prueba") is False


def test_format_nuevo_usa_markdown_whatsapp():
    anuncio = {
        "plaza": "Técnico/a Superior de Telecomunicaciones",
        "entidad": "Diputación de Alicante",
        "vacantes": "1",
        "fecha_ini": "2026-07-01",
        "fecha_fin": "2026-07-20",
        "url_bases": "https://sede.diputacionalicante.es/bases/11357.pdf",
    }
    texto = format_nuevo(anuncio, perfil="telecomunicaciones_tic")

    assert "*NUEVA CONVOCATORIA*" in texto
    assert "*Plaza:* Técnico/a Superior de Telecomunicaciones" in texto
    assert "*Entidad:* Diputación de Alicante" in texto
    assert "*Vacantes:* 1" in texto
    assert "*Plazo:* 2026-07-01 - 2026-07-20" in texto
    assert "https://sede.diputacionalicante.es/bases/11357.pdf" in texto
    assert "*Perfil coincidente:* telecomunicaciones_tic" in texto
    # Nada de HTML de Telegram
    assert "<b>" not in texto
    assert "<a href" not in texto


def test_format_nuevo_sin_campos_opcionales_no_rompe():
    anuncio = {"plaza": "Auxiliar Administrativo", "entidad": "Ayuntamiento de Benidorm"}
    texto = format_nuevo(anuncio, perfil="perfil_x")
    assert "*Plaza:* Auxiliar Administrativo" in texto
    assert "*Entidad:* Ayuntamiento de Benidorm" in texto
    assert "*Bases:* (sin enlace disponible)" in texto


def test_format_actualizado_usa_diff_de_obs():
    anuncio = {
        "plaza": "Técnico/a Superior de Telecomunicaciones",
        "entidad": "Diputación de Alicante",
        "obs": "Publicado en BOP núm. 100. Ampliado plazo según BOP núm. 120.",
        "url_bases": "https://sede.diputacionalicante.es/bases/11357.pdf",
    }
    texto = format_actualizado(
        anuncio,
        perfil="telecomunicaciones_tic",
        obs_anterior="Publicado en BOP núm. 100.",
    )

    assert "*ACTUALIZACIÓN*" in texto
    # obs_diff_suffix recorta puntuación final del texto añadido
    assert "_Novedad en Obs:_ Ampliado plazo según BOP núm. 120" in texto
    assert "*Perfil coincidente:* telecomunicaciones_tic" in texto
    assert "<b>" not in texto
