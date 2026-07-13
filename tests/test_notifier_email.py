"""Tests offline de notifications/email_smtp.py (sin tocar la red).

Se sustituyen smtplib.SMTP y smtplib.SMTP_SSL por dobles que registran
las llamadas, de forma que ningun test abre conexiones reales.
"""

import smtplib
from email import message_from_string

import pytest

from notifications.email_smtp import EmailNotifier

VARS_ENTORNO = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"]

MENSAJE_EJEMPLO = (
    "<b>Nueva convocatoria (BOP Alicante)</b>\n"
    "Bolsa de Ingeniero/a de Telecomunicaciones A1 - Ayto de Elche\n"
    "Plazo: 17/06/2026 a 01/07/2026\n"
    '<a href="https://www.dip-alicante.es/bop2/">Enlace</a>'
)


class ServidorSmtpFalso:
    """Doble de smtplib.SMTP: registra host, puerto, timeout y llamadas."""

    instancias = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_llamado = False
        self.login_args = None
        self.sendmail_args = None
        type(self).instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.starttls_llamado = True

    def login(self, usuario, password):
        self.login_args = (usuario, password)

    def sendmail(self, remitente, destinatarios, mensaje):
        self.sendmail_args = (remitente, destinatarios, mensaje)


class ServidorSmtpSslFalso(ServidorSmtpFalso):
    """Doble de smtplib.SMTP_SSL, con registro de instancias propio."""

    instancias = []


class ServidorProhibido:
    """Doble que falla si alguien intenta abrir una conexion SMTP."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("No deberia abrirse ninguna conexion SMTP")


@pytest.fixture
def entorno_smtp(monkeypatch):
    """Configura env vars validas y sustituye smtplib por los dobles."""
    for var in VARS_ENTORNO:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.es")
    monkeypatch.setenv("SMTP_USER", "avisos@ejemplo.es")
    monkeypatch.setenv("SMTP_PASSWORD", "secreta")
    monkeypatch.setenv("EMAIL_TO", "opositor@ejemplo.es")

    ServidorSmtpFalso.instancias = []
    ServidorSmtpSslFalso.instancias = []
    monkeypatch.setattr(smtplib, "SMTP", ServidorSmtpFalso)
    monkeypatch.setattr(smtplib, "SMTP_SSL", ServidorSmtpSslFalso)


def _extraer_partes(mensaje_crudo: str) -> dict:
    """Devuelve {content_type: cuerpo_decodificado} del correo enviado."""
    correo = message_from_string(mensaje_crudo)
    assert correo.is_multipart()
    return {
        parte.get_content_type(): parte.get_payload(decode=True).decode("utf-8")
        for parte in correo.walk()
        if parte.get_content_type() in ("text/plain", "text/html")
    }


def test_sin_config_devuelve_false_sin_excepciones(monkeypatch):
    for var in VARS_ENTORNO:
        monkeypatch.delenv(var, raising=False)
    # Si el notificador intentase conectar sin config, el doble lanza AssertionError.
    monkeypatch.setattr(smtplib, "SMTP", ServidorProhibido)
    monkeypatch.setattr(smtplib, "SMTP_SSL", ServidorProhibido)

    notifier = EmailNotifier()
    assert notifier.send_message(MENSAJE_EJEMPLO) is False


def test_config_parcial_devuelve_false(monkeypatch):
    for var in VARS_ENTORNO:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.es")
    monkeypatch.setenv("SMTP_USER", "avisos@ejemplo.es")
    # Faltan SMTP_PASSWORD y EMAIL_TO.
    monkeypatch.setattr(smtplib, "SMTP", ServidorProhibido)
    monkeypatch.setattr(smtplib, "SMTP_SSL", ServidorProhibido)

    assert EmailNotifier().send_message(MENSAJE_EJEMPLO) is False


def test_envio_ok_puerto_587_starttls_y_payload(entorno_smtp):
    notifier = EmailNotifier()
    assert notifier.send_message(MENSAJE_EJEMPLO) is True

    # Se uso SMTP (STARTTLS), no SMTP_SSL.
    assert len(ServidorSmtpFalso.instancias) == 1
    assert ServidorSmtpSslFalso.instancias == []

    servidor = ServidorSmtpFalso.instancias[0]
    assert servidor.host == "smtp.ejemplo.es"
    assert servidor.port == 587  # default cuando SMTP_PORT no esta definido
    assert servidor.timeout == 20
    assert servidor.starttls_llamado is True
    assert servidor.login_args == ("avisos@ejemplo.es", "secreta")

    remitente, destinatarios, mensaje_crudo = servidor.sendmail_args
    # EMAIL_FROM no definido -> remitente por defecto = SMTP_USER.
    assert remitente == "avisos@ejemplo.es"
    assert destinatarios == ["opositor@ejemplo.es"]

    partes = _extraer_partes(mensaje_crudo)
    assert set(partes) == {"text/plain", "text/html"}

    # La parte HTML conserva el formato y convierte \n en <br>.
    assert "<b>Nueva convocatoria (BOP Alicante)</b>" in partes["text/html"]
    assert "<br>" in partes["text/html"]

    # La parte de texto plano no lleva etiquetas HTML.
    assert "<b>" not in partes["text/plain"]
    assert "<br>" not in partes["text/plain"]
    assert "Bolsa de Ingeniero/a de Telecomunicaciones A1 - Ayto de Elche" in partes["text/plain"]


def test_asunto_primera_linea_sin_html_con_prefijo(entorno_smtp):
    EmailNotifier().send_message(MENSAJE_EJEMPLO)

    _, _, mensaje_crudo = ServidorSmtpFalso.instancias[0].sendmail_args
    correo = message_from_string(mensaje_crudo)
    assert correo["Subject"] == "[OpoRadar] Nueva convocatoria (BOP Alicante)"


def test_asunto_recortado_a_100_caracteres(entorno_smtp):
    mensaje = "<b>" + ("A" * 150) + "</b>\nresto del cuerpo"
    EmailNotifier().send_message(mensaje)

    _, _, mensaje_crudo = ServidorSmtpFalso.instancias[0].sendmail_args
    correo = message_from_string(mensaje_crudo)
    assert correo["Subject"] == "[OpoRadar] " + "A" * 100


def test_puerto_465_usa_smtp_ssl_sin_starttls(entorno_smtp, monkeypatch):
    monkeypatch.setenv("SMTP_PORT", "465")

    notifier = EmailNotifier()
    assert notifier.send_message(MENSAJE_EJEMPLO) is True

    assert ServidorSmtpFalso.instancias == []
    assert len(ServidorSmtpSslFalso.instancias) == 1

    servidor = ServidorSmtpSslFalso.instancias[0]
    assert servidor.port == 465
    assert servidor.timeout == 20
    assert servidor.starttls_llamado is False  # con SSL directo no hay STARTTLS
    assert servidor.sendmail_args is not None


def test_email_from_explicito_se_respeta(entorno_smtp, monkeypatch):
    monkeypatch.setenv("EMAIL_FROM", "oporadar@ejemplo.es")

    EmailNotifier().send_message(MENSAJE_EJEMPLO)

    remitente, _, mensaje_crudo = ServidorSmtpFalso.instancias[0].sendmail_args
    assert remitente == "oporadar@ejemplo.es"
    assert message_from_string(mensaje_crudo)["From"] == "oporadar@ejemplo.es"


def test_error_de_envio_devuelve_false(entorno_smtp, monkeypatch):
    class ServidorQueFalla(ServidorSmtpFalso):
        instancias = []

        def sendmail(self, *args):
            raise smtplib.SMTPException("fallo simulado")

    monkeypatch.setattr(smtplib, "SMTP", ServidorQueFalla)

    assert EmailNotifier().send_message(MENSAJE_EJEMPLO) is False
