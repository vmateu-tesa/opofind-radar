"""Notificador SECUNDARIO de OpoRadar: WhatsApp Cloud API (Meta).

Telegram es el canal PRINCIPAL recomendado frente a WhatsApp: los mensajes de
texto libre de un bot de Telegram no caducan nunca, mientras que WhatsApp
Cloud API solo permite texto libre dentro de una ventana de servicio de 24h
desde el último mensaje del usuario -- pasado ese plazo hay que recurrir a
plantillas (HSM) previamente revisadas y aprobadas por Meta, un trámite que
puede tardar días y que puede rechazar el contenido. Telegram, además, solo
requiere un token de bot (sin número de teléfono verificado ni cuenta de
WhatsApp Business). Para un proyecto personal como OpoRadar eso es mucho
menos fricción operativa y menos puntos de fallo; WhatsApp se mantiene aquí
como aviso adicional opcional en el móvil, con el fallback a plantilla
resuelto automáticamente cuando la ventana de 24h está cerrada.

Como app.notifier_telegram, este módulo no decide QUÉ notificar ni evita
duplicados -- eso es responsabilidad de quien lo orquesta (compara con
app.db.has_been_notified antes de llamar aquí y registra el envío con
app.db.record_notification después). Aquí solo vive el "cómo": formatear en
el markdown limitado de WhatsApp y enviar.
"""

import logging

import requests

from app.config import settings
from app.utils import obs_diff_suffix

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v20.0"
GRAPH_API_BASE = "https://graph.facebook.com"
REQUEST_TIMEOUT = 20

# Códigos de error de Meta que indican que la ventana de servicio de 24h está
# cerrada y hay que reenviar con plantilla. 131047 es el específico de
# "re-engagement message"; 131026 ("message undeliverable") puede darse por
# el mismo motivo en algunos casos, así que también dispara el fallback.
REENGAGEMENT_ERROR_CODES = {131047, 131026}


def _api_url() -> str:
    return f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{settings.whatsapp_phone_number_id}/messages"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.whatsapp_token}",
        "Content-Type": "application/json",
    }


def _is_reengagement_error(response: requests.Response) -> bool:
    """Detecta si la respuesta de error de Meta corresponde a la ventana de
    24h cerrada (hay que reintentar con plantilla en vez de texto libre)."""
    try:
        payload = response.json()
    except ValueError:
        return False
    error = payload.get("error") or {}
    return error.get("code") in REENGAGEMENT_ERROR_CODES or error.get("error_subcode") in REENGAGEMENT_ERROR_CODES


def _send_text(text: str) -> requests.Response:
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": settings.whatsapp_to_number,
        "type": "text",
        "text": {"body": text, "preview_url": False},
    }
    return requests.post(_api_url(), headers=_headers(), json=body, timeout=REQUEST_TIMEOUT)


def _send_template(text: str) -> requests.Response:
    """Fallback cuando la ventana de 24h está cerrada. Asume una plantilla
    pre-aprobada en Meta Business Manager con un único parámetro de cuerpo de
    tipo texto, al que se le pasa el contenido íntegro del aviso (recortado a
    un tamaño razonable: WhatsApp limita la longitud de los parámetros de
    plantilla)."""
    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": settings.whatsapp_to_number,
        "type": "template",
        "template": {
            "name": settings.whatsapp_template_name,
            "language": {"code": "es"},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": text[:1024]}],
                }
            ],
        },
    }
    return requests.post(_api_url(), headers=_headers(), json=body, timeout=REQUEST_TIMEOUT)


def send_message(text: str) -> bool:
    """Envía `text` por WhatsApp Cloud API al número configurado (settings.whatsapp_to_number).

    Intenta primero un mensaje de texto libre (type='text'). Si Meta responde
    que la ventana de servicio de 24h está cerrada (código de error de
    re-engagement, típicamente 131047), reintenta automáticamente con una
    plantilla pre-aprobada (type='template', settings.whatsapp_template_name,
    idioma 'es'). Devuelve True si el envío (texto o plantilla) tuvo éxito,
    False en cualquier otro caso (error HTTP no recuperable, excepción de
    red...). En DRY_RUN no se llama a la API real: solo se loguea."""
    if settings.dry_run:
        logger.info("[DRY_RUN] Enviaría a WhatsApp (con fallback a plantilla si procede): %s", text)
        return True

    try:
        response = _send_text(text)
    except requests.RequestException as exc:
        logger.error("Error de red enviando WhatsApp (texto libre): %s", exc)
        return False

    if response.ok:
        logger.info("Mensaje de WhatsApp enviado (texto libre).")
        return True

    if not _is_reengagement_error(response):
        logger.error("Fallo enviando WhatsApp (HTTP %s): %s", response.status_code, response.text)
        return False

    logger.info(
        "Ventana de 24h cerrada en WhatsApp; reintentando con plantilla '%s'.",
        settings.whatsapp_template_name,
    )
    try:
        template_response = _send_template(text)
    except requests.RequestException as exc:
        logger.error("Error de red enviando WhatsApp (plantilla): %s", exc)
        return False

    if template_response.ok:
        logger.info("Mensaje de WhatsApp enviado (plantilla).")
        return True

    logger.error(
        "Fallo enviando WhatsApp por plantilla (HTTP %s): %s",
        template_response.status_code, template_response.text,
    )
    return False


def format_nuevo(anuncio: dict, perfil: str) -> str:
    """Construye el mensaje para una convocatoria NUEVA detectada, en el
    markdown limitado de WhatsApp (*negrita*, _cursiva_) -- sin HTML ni
    enlaces con texto alternativo como en Telegram, así que la URL de bases
    se escribe literal.

    `anuncio` es el dict de campos habitual (plaza, entidad, vacantes,
    url_bases, fecha_ini, fecha_fin, ...); `perfil` es el nombre del perfil
    de alertas que ha hecho match (config/alertas.yaml)."""
    plaza = str(anuncio.get("plaza") or "(sin especificar)")
    entidad = str(anuncio.get("entidad") or "(sin especificar)")
    vacantes = str(anuncio.get("vacantes") or "(no indicado)")
    fecha_ini = str(anuncio.get("fecha_ini") or "(no indicada)")
    fecha_fin = str(anuncio.get("fecha_fin") or "(no indicada)")
    url_bases = anuncio.get("url_bases") or ""

    lineas = [
        "🚨 *NUEVA CONVOCATORIA*",
        "",
        f"*Plaza:* {plaza}",
        f"*Entidad:* {entidad}",
        f"*Vacantes:* {vacantes}",
        f"*Plazo:* {fecha_ini} - {fecha_fin}",
    ]
    lineas.append(f"*Bases:* {url_bases}" if url_bases else "*Bases:* (sin enlace disponible)")
    lineas.append(f"*Perfil coincidente:* {perfil}")

    return "\n".join(lineas)


def format_actualizado(anuncio: dict, perfil: str, obs_anterior: str) -> str:
    """Construye el mensaje para una convocatoria ya conocida que se ha
    ACTUALIZADO (típicamente el campo Obs ha crecido con una nueva
    publicación BOP/DOGV/BOE), en el markdown limitado de WhatsApp. Usa
    app.utils.obs_diff_suffix para mostrar solo lo añadido cuando es posible
    detectarlo, igual que app.notifier_telegram.format_actualizado."""
    plaza = str(anuncio.get("plaza") or "(sin especificar)")
    entidad = str(anuncio.get("entidad") or "(sin especificar)")
    url_bases = anuncio.get("url_bases") or ""

    diff = obs_diff_suffix(obs_anterior, str(anuncio.get("obs") or ""))

    lineas = [
        "🔄 *ACTUALIZACIÓN*",
        "",
        f"*Plaza:* {plaza}",
        f"*Entidad:* {entidad}",
        f"_Novedad en Obs:_ {diff}",
    ]
    if url_bases:
        lineas.append(f"*Bases:* {url_bases}")
    lineas.append(f"*Perfil coincidente:* {perfil}")

    return "\n".join(lineas)
