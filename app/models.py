"""Contrato común entre scrapers y el resto del sistema.

Todo scraper expone `fetch() -> list[AnuncioRaw]`. Nada más se asume de un
scraper: cómo obtiene los datos (HTML, RSS, JSON) es asunto suyo.
"""

from dataclasses import dataclass, field


@dataclass
class AnuncioRaw:
    fuente: str
    external_id: str
    plaza: str
    entidad: str
    vacantes: str = ""
    url_bases: str = ""
    fecha_ini: str = ""
    fecha_fin: str = ""
    obs: str = ""
    raw_data: dict = field(default_factory=dict)
