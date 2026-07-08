"""Carga de configuración: alertas.yaml (releído en cada ciclo) y variables
de entorno (canales, DRY_RUN, rutas, credenciales)."""

import os

import yaml

DEFAULT_ALERTAS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "alertas.yaml")


def load_profiles(path: str = DEFAULT_ALERTAS_PATH) -> list[dict]:
    """Lee alertas.yaml desde disco cada vez que se llama (sin caché): permite
    editar el fichero y que el siguiente ciclo de cron lo recoja sin reiniciar nada."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    profiles = data.get("profiles", [])
    validated = []
    for p in profiles:
        if not p.get("enabled", True):
            continue
        if not p.get("name") or not p.get("include_any"):
            raise ValueError(f"Perfil de alerta inválido (falta name o include_any): {p}")
        p.setdefault("fields", ["plaza", "entidad", "obs"])
        p.setdefault("channels", ["telegram"])
        p.setdefault("exclude_any", [])
        validated.append(p)
    return validated


def env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    """Lectura de variables de entorno, evaluada de forma perezosa (no en import)."""

    @property
    def dry_run(self) -> bool:
        return env_bool("DRY_RUN", default=True)

    @property
    def db_path(self) -> str:
        return os.environ.get("DB_PATH", os.path.join("data", "oporadar.db"))

    @property
    def telegram_enabled(self) -> bool:
        return env_bool("TELEGRAM_ENABLED", default=True)

    @property
    def whatsapp_enabled(self) -> bool:
        return env_bool("WHATSAPP_ENABLED", default=False)

    @property
    def telegram_bot_token(self) -> str:
        return os.environ.get("TELEGRAM_BOT_TOKEN", "")

    @property
    def telegram_chat_id(self) -> str:
        return os.environ.get("TELEGRAM_CHAT_ID", "")

    @property
    def whatsapp_token(self) -> str:
        return os.environ.get("WHATSAPP_TOKEN", "")

    @property
    def whatsapp_phone_number_id(self) -> str:
        return os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

    @property
    def whatsapp_to_number(self) -> str:
        return os.environ.get("WHATSAPP_TO_NUMBER", "")

    @property
    def whatsapp_template_name(self) -> str:
        return os.environ.get("WHATSAPP_TEMPLATE_NAME", "opo_alerta")


settings = Settings()
