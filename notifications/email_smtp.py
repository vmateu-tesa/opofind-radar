"""Notificador por correo electronico via SMTP.

Usa exclusivamente la stdlib (smtplib + email.mime), sin dependencias nuevas.
Recibe mensajes con HTML estilo Telegram (<b>...</b>, saltos \\n) y los envia
como correo multipart con alternativa text/plain y text/html.
"""

import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape

from notifications.base import BaseNotifier


class EmailNotifier(BaseNotifier):
    """Envia notificaciones por email usando SMTP (STARTTLS en 587, SSL en 465)."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        remitente: str = None,
        destinatario: str = None,
    ):
        self.host = host or os.getenv("SMTP_HOST")
        self.port = int(port or os.getenv("SMTP_PORT") or 587)
        self.user = user or os.getenv("SMTP_USER")
        self.password = password or os.getenv("SMTP_PASSWORD")
        self.remitente = remitente or os.getenv("EMAIL_FROM") or self.user
        self.destinatario = destinatario or os.getenv("EMAIL_TO")

    def send_message(self, message: str) -> bool:
        if not self.host or not self.user or not self.password or not self.destinatario:
            print(
                "EmailNotifier: Configuracion SMTP incompleta "
                "(revisa SMTP_HOST, SMTP_USER, SMTP_PASSWORD y EMAIL_TO)."
            )
            return False

        correo = self._construir_correo(message)

        try:
            if self.port == 465:
                # SSL directo desde el primer byte (SMTPS).
                with smtplib.SMTP_SSL(self.host, self.port, timeout=20) as servidor:
                    servidor.login(self.user, self.password)
                    servidor.sendmail(
                        self.remitente, [self.destinatario], correo.as_string()
                    )
            else:
                # Conexion en claro + STARTTLS (caso tipico del puerto 587).
                with smtplib.SMTP(self.host, self.port, timeout=20) as servidor:
                    servidor.starttls()
                    servidor.login(self.user, self.password)
                    servidor.sendmail(
                        self.remitente, [self.destinatario], correo.as_string()
                    )
            return True
        except Exception as e:
            print(f"Error enviando email: {e}")
            return False

    def _construir_correo(self, message: str) -> MIMEMultipart:
        """Monta el correo multipart/alternative (text/plain + text/html)."""
        correo = MIMEMultipart("alternative")
        correo["Subject"] = self._construir_asunto(message)
        correo["From"] = self.remitente
        correo["To"] = self.destinatario

        # Alternativa en texto plano: sin etiquetas HTML ni entidades.
        texto_plano = self._sin_etiquetas_html(message)

        # Cuerpo HTML: el mensaje ya trae etiquetas estilo Telegram (<b>...),
        # solo convertimos los saltos de linea y lo envolvemos en algo legible.
        cuerpo_html = message.replace("\n", "<br>\n")
        html = (
            '<div style="font-family: Arial, Helvetica, sans-serif; '
            'font-size: 14px; line-height: 1.5; color: #222222; '
            'max-width: 640px; margin: 0 auto; padding: 16px;">\n'
            f"{cuerpo_html}\n"
            "</div>"
        )

        # El orden importa: la ultima parte adjuntada es la preferida.
        correo.attach(MIMEText(texto_plano, "plain", "utf-8"))
        correo.attach(MIMEText(html, "html", "utf-8"))
        return correo

    def _construir_asunto(self, message: str) -> str:
        """Asunto: primera linea sin etiquetas HTML, maximo 100 caracteres."""
        primera_linea = message.split("\n", 1)[0]
        limpia = self._sin_etiquetas_html(primera_linea)
        return f"[OpoRadar] {limpia[:100]}"

    @staticmethod
    def _sin_etiquetas_html(texto: str) -> str:
        """Quita etiquetas HTML y decodifica entidades (&amp; -> &, etc.)."""
        sin_etiquetas = re.sub(r"<[^>]+>", "", texto)
        return unescape(sin_etiquetas).strip()
