"""Utilidades compartidas por todos los scrapers: rate limiting y cabeceras HTTP.

Todas las fuentes de sede.diputacionalicante.es son un servicio público sin
prisa por un cron diario: se respeta un intervalo mínimo entre peticiones.
"""

import time

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OpoRadarBot/1.0 "
        "(+uso personal, cron diario; contacto: vmateu.bee@gmail.com)"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

DEFAULT_TIMEOUT = 20


class RateLimiter:
    """Fuerza un intervalo mínimo entre peticiones sucesivas al mismo host."""

    def __init__(self, min_interval_seconds: float = 3.0):
        self.min_interval = min_interval_seconds
        self._last_call = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last_call
        remaining = self.min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()


# Rate limiter compartido para todo sede.diputacionalicante.es (tabla + RSS + BOP),
# para no exceder 1 petición cada pocos segundos a ese dominio en conjunto.
diputacion_rate_limiter = RateLimiter(min_interval_seconds=3.0)
