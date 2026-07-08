"""Motor de coincidencias multi-perfil de OpoRadar.

Un mismo anuncio puede interesar a varios perfiles de alerta a la vez (p.ej.
una plaza de "Técnico de Sistemas de Información" encaja tanto en
telecomunicaciones_tic como en gestion_proyectos_admin_electronica). Por eso
`evaluate` no se detiene en el primer perfil que coincide: recorre todos.

Reglas de coincidencia por perfil (ver también los comentarios de
config/alertas.yaml):
  1. Se concatena el texto normalizado (sin acentos, minúsculas) de los
     campos indicados en `fields` del perfil.
  2. Si CUALQUIER patrón de `exclude_any` hace match (re.search) sobre ese
     texto, el perfil queda descartado inmediatamente para este anuncio,
     aunque también matchee algún include_any.
  3. Si no ha sido excluido y CUALQUIER patrón de `include_any` hace match,
     el perfil coincide.
"""

import re

from app.utils import normalize_text


def _build_text(anuncio: dict, fields: list[str]) -> str:
    """Concatena el texto normalizado de los campos indicados del anuncio.

    Campos ausentes o vacíos en el dict simplemente no aportan texto (no es
    un error: no todos los anuncios rellenan todos los campos)."""
    partes = [normalize_text(str(anuncio.get(campo, "") or "")) for campo in fields]
    return " ".join(p for p in partes if p)


def evaluate(anuncio: dict, profiles: list[dict]) -> list[str]:
    """Devuelve los nombres de los perfiles de `profiles` que coinciden con
    `anuncio`. `anuncio` es un dict (típicamente el record devuelto por
    app.db.upsert_anuncio o un AnuncioRaw convertido a dict) con al menos
    las claves usadas en los `fields` de cada perfil (plaza, entidad, obs)."""
    coincidencias = []
    for perfil in profiles:
        fields = perfil.get("fields") or ["plaza", "entidad", "obs"]
        texto = _build_text(anuncio, fields)

        excluido = any(re.search(patron, texto) for patron in perfil.get("exclude_any") or [])
        if excluido:
            continue

        incluido = any(re.search(patron, texto) for patron in perfil.get("include_any") or [])
        if incluido:
            coincidencias.append(perfil["name"])

    return coincidencias
