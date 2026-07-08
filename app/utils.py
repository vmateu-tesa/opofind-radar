"""Utilidades compartidas: normalización de texto, hash de contenido, IDs estables."""

import hashlib
import re
import unicodedata


def normalize_text(text: str) -> str:
    """Minúsculas, sin acentos, espacios colapsados. Para matching por keywords."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    sin_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin_acentos.lower()).strip()


def compute_content_hash(*parts: str) -> str:
    """Hash estable del contenido completo de un anuncio, para detectar cambios
    (incluida la ampliación del campo Obs con nuevas publicaciones BOP/DOGV/BOE)."""
    canonical = "|".join((p or "").strip() for p in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


_PDF_ID_RE = re.compile(r"/(\d+)\.pdf(?:$|[?#])", re.IGNORECASE)


def extract_pdf_id(url: str) -> str | None:
    """Extrae el ID numérico estable del nombre de fichero PDF (p.ej. 11357.pdf -> '11357')."""
    if not url:
        return None
    match = _PDF_ID_RE.search(url)
    if match:
        return match.group(1)
    return None


def stable_fallback_id(*parts: str) -> str:
    """ID estable de reserva cuando no hay un identificador natural (p.ej. sin PDF).
    Usa un hash corto y determinista de los campos dados (típicamente título+fecha)."""
    canonical = "|".join((p or "").strip() for p in parts)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def obs_diff_suffix(old_obs: str, new_obs: str) -> str:
    """Heurística simple: si el nuevo Obs añade texto al final del anterior (patrón
    habitual en la tabla de la Diputación), devuelve solo lo añadido. Si no, devuelve
    el Obs completo con una nota de que el contenido cambió de forma no incremental."""
    old_obs = (old_obs or "").strip()
    new_obs = (new_obs or "").strip()
    if not old_obs:
        return new_obs
    if new_obs.startswith(old_obs):
        added = new_obs[len(old_obs):].strip(" .;-\n")
        return added if added else "(sin texto adicional detectado)"
    return f"(contenido modificado, no solo ampliado)\n{new_obs}"
