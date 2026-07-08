"""Notificador de Telegram: canal PRINCIPAL recomendado de OpoRadar.

Envía mensajes formateados en HTML a un chat de Telegram vía la Bot API
(`sendMessage`). En DRY_RUN (por defecto) no llama a la red: solo loguea lo
que enviaría, para poder probar el formato sin token ni chat real.

Este módulo no decide QUÉ notificar ni evita duplicados -- eso es
responsabilidad de quien lo orquesta (compara con app.db.has_been_notified
antes de llamar aquí y registra el envío con app.db.record_notification
después). Aquí solo vive el "cómo": formatear y enviar.
"""

import html
import logging
import time

import requests

from app.config import settings
from app.utils import obs_diff_suffix

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

# Telegram trocea mensajes por encima de este límite de caracteres (4096
# exactos es el límite real de la API; se deja margen para no rozarlo).
MAX_MESSAGE_LENGTH = 4096

# Al trocear buscamos un salto de línea antes de este umbral para no cortar
# una línea por la mitad.
_CHUNK_TARGET = 4000


def _escape_html(text: str) -> str:
    """Escapa &, < y > para que el texto sea seguro dentro de HTML de Telegram.

    Telegram con parse_mode='HTML' solo requiere escapar estos tres
    caracteres (a diferencia del HTML general, no hace falta escapar
    comillas fuera de atributos)."""
    return html.escape(text or "", quote=False)


def _split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Trocea `text` en fragmentos de como máximo `max_length` caracteres.

    Intenta cortar por un salto de línea cercano al límite para no partir
    una etiqueta HTML o una palabra por la mitad. Si un único "párrafo" ya
    supera el límite (caso raro), se corta en seco como último recurso."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    remaining = text
    target = min(_CHUNK_TARGET, max_length)
    while len(remaining) > max_length:
        cut = remaining.rfind("\n", 0, target)
        if cut <= 0:
            # Sin salto de línea razonable: corte duro para respetar el límite.
            cut = max_length
        chunks.append(remaining[:cut].rstrip("\n"))
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def _send_single(text: str) -> bool:
    """Envía un único fragmento (ya troceado si hacía falta) a la API de Telegram.
    Reintenta UNA vez si Telegram responde 429 (rate limit), esperando
    `retry_after` segundos."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }

    for intento in (1, 2):
        try:
            resp = requests.post(url, json=payload, timeout=20)
        except requests.RequestException:
            logger.exception("Error de red enviando mensaje a Telegram")
            return False

        if resp.status_code == 200:
            return True

        if resp.status_code == 429 and intento == 1:
            retry_after = 1
            try:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 1)
            except (ValueError, AttributeError):
                pass
            logger.warning(
                "Telegram devolvió 429 (rate limit); reintentando en %s s", retry_after
            )
            time.sleep(retry_after)
            continue

        logger.error(
            "Telegram respondió %s al enviar mensaje: %s", resp.status_code, resp.text
        )
        return False

    return False


def send_message(text: str) -> bool:
    """Envía `text` (HTML ya construido) al chat configurado en Telegram.

    En DRY_RUN no llama a la API: loguea el texto completo y devuelve True,
    para poder probar el flujo sin credenciales reales. Si el mensaje supera
    el límite de Telegram, se trocea en varios envíos; se considera éxito
    solo si TODOS los fragmentos se envían correctamente."""
    if settings.dry_run:
        logging.info("[DRY_RUN] Enviaría a Telegram: %s", text)
        return True

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.error(
            "No se puede enviar a Telegram: falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID"
        )
        return False

    fragmentos = _split_message(text)
    exito_total = True
    for fragmento in fragmentos:
        if not _send_single(fragmento):
            exito_total = False
    return exito_total


def format_nuevo(anuncio: dict, perfil: str) -> str:
    """Construye el mensaje HTML para una convocatoria NUEVA detectada.

    `anuncio` es el dict de campos habitual (plaza, entidad, vacantes,
    url_bases, fecha_ini, fecha_fin, ...); `perfil` es el nombre del perfil
    de alertas que ha hecho match (config/alertas.yaml)."""
    plaza = _escape_html(str(anuncio.get("plaza") or "(sin especificar)"))
    entidad = _escape_html(str(anuncio.get("entidad") or "(sin especificar)"))
    vacantes = _escape_html(str(anuncio.get("vacantes") or "(no indicado)"))
    fecha_ini = _escape_html(str(anuncio.get("fecha_ini") or "(no indicada)"))
    fecha_fin = _escape_html(str(anuncio.get("fecha_fin") or "(no indicada)"))
    url_bases = anuncio.get("url_bases") or ""
    perfil_html = _escape_html(perfil)

    lineas = [
        "🚨 <b>NUEVA CONVOCATORIA</b>",
        "",
        f"<b>Plaza:</b> {plaza}",
        f"<b>Entidad:</b> {entidad}",
        f"<b>Vacantes:</b> {vacantes}",
        f"<b>Plazo:</b> {fecha_ini} - {fecha_fin}",
    ]
    if url_bases:
        lineas.append(f'<b>Bases:</b> <a href="{_escape_html(url_bases)}">{_escape_html(url_bases)}</a>')
    else:
        lineas.append("<b>Bases:</b> (sin enlace disponible)")
    lineas.append(f"<b>Perfil coincidente:</b> {perfil_html}")

    return "\n".join(lineas)


def format_actualizado(anuncio: dict, perfil: str, obs_anterior: str) -> str:
    """Construye el mensaje HTML para una convocatoria ya conocida que se ha
    ACTUALIZADO (típicamente el campo Obs ha crecido con una nueva publicación
    BOP/DOGV/BOE). Usa app.utils.obs_diff_suffix para mostrar solo lo añadido
    cuando es posible detectarlo."""
    plaza = _escape_html(str(anuncio.get("plaza") or "(sin especificar)"))
    entidad = _escape_html(str(anuncio.get("entidad") or "(sin especificar)"))
    url_bases = anuncio.get("url_bases") or ""
    perfil_html = _escape_html(perfil)

    diff = obs_diff_suffix(obs_anterior, str(anuncio.get("obs") or ""))
    diff_html = _escape_html(diff)

    lineas = [
        "🔄 <b>ACTUALIZACIÓN</b>",
        "",
        f"<b>Plaza:</b> {plaza}",
        f"<b>Entidad:</b> {entidad}",
        f"<b>Novedad en Obs:</b> {diff_html}",
    ]
    if url_bases:
        lineas.append(f'<b>Bases:</b> <a href="{_escape_html(url_bases)}">{_escape_html(url_bases)}</a>')
    lineas.append(f"<b>Perfil coincidente:</b> {perfil_html}")

    return "\n".join(lineas)
