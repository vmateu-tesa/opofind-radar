"""Persistencia SQLite. Sin ORM: el esquema es pequeño y estable.

Tabla `anuncios`: una fila por proceso/convocatoria detectado, clave única
(fuente, external_id). `content_hash` cubre TODOS los campos (incluido Obs),
así que una fila ya conocida cuyo Obs se ha ampliado se detecta como
'actualizado', no como duplicado silencioso.

Tabla `notificaciones`: registro de qué se ha enviado ya (por perfil de
alerta + canal + hash de contenido en el momento del envío), para no
reenviar lo mismo pero sí notificar de nuevo si el contenido vuelve a
cambiar más adelante.
"""

import json
import os
import sqlite3

from app.models import AnuncioRaw
from app.utils import compute_content_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS anuncios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fuente TEXT NOT NULL,
    external_id TEXT NOT NULL,
    plaza TEXT,
    entidad TEXT,
    vacantes TEXT,
    url_bases TEXT,
    fecha_ini TEXT,
    fecha_fin TEXT,
    obs TEXT,
    content_hash TEXT NOT NULL,
    raw_data TEXT,
    first_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(fuente, external_id)
);

CREATE TABLE IF NOT EXISTS notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    anuncio_id INTEGER NOT NULL REFERENCES anuncios(id),
    perfil TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK(tipo IN ('nuevo','actualizado')),
    canal TEXT NOT NULL CHECK(canal IN ('telegram','whatsapp')),
    content_hash_notificado TEXT NOT NULL,
    contenido TEXT,
    exito INTEGER NOT NULL DEFAULT 1,
    enviado_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notif_lookup
    ON notificaciones(anuncio_id, perfil, canal, content_hash_notificado);

CREATE INDEX IF NOT EXISTS idx_anuncios_fuente ON anuncios(fuente);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    directory = os.path.dirname(db_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("raw_data"):
        try:
            d["raw_data"] = json.loads(d["raw_data"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def upsert_anuncio(conn: sqlite3.Connection, item: AnuncioRaw) -> tuple[int, str, dict]:
    """Inserta o actualiza un anuncio. Devuelve (id, status, registro_dict) donde
    status es 'nuevo', 'actualizado' o 'sin_cambios'."""
    new_hash = compute_content_hash(
        item.plaza, item.entidad, item.vacantes, item.url_bases,
        item.fecha_ini, item.fecha_fin, item.obs,
    )
    raw_json = json.dumps(item.raw_data or {}, ensure_ascii=False, sort_keys=True, default=str)

    existing = conn.execute(
        "SELECT * FROM anuncios WHERE fuente = ? AND external_id = ?",
        (item.fuente, item.external_id),
    ).fetchone()

    if existing is None:
        cur = conn.execute(
            """INSERT INTO anuncios
               (fuente, external_id, plaza, entidad, vacantes, url_bases,
                fecha_ini, fecha_fin, obs, content_hash, raw_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (item.fuente, item.external_id, item.plaza, item.entidad, item.vacantes,
             item.url_bases, item.fecha_ini, item.fecha_fin, item.obs, new_hash, raw_json),
        )
        conn.commit()
        anuncio_id = cur.lastrowid
        record = _row_to_dict(conn.execute("SELECT * FROM anuncios WHERE id = ?", (anuncio_id,)).fetchone())
        return anuncio_id, "nuevo", record

    anuncio_id = existing["id"]
    if existing["content_hash"] != new_hash:
        conn.execute(
            """UPDATE anuncios SET plaza=?, entidad=?, vacantes=?, url_bases=?,
               fecha_ini=?, fecha_fin=?, obs=?, content_hash=?, raw_data=?,
               last_updated=CURRENT_TIMESTAMP, last_seen_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (item.plaza, item.entidad, item.vacantes, item.url_bases, item.fecha_ini,
             item.fecha_fin, item.obs, new_hash, raw_json, anuncio_id),
        )
        conn.commit()
        record = _row_to_dict(conn.execute("SELECT * FROM anuncios WHERE id = ?", (anuncio_id,)).fetchone())
        record["_obs_anterior"] = existing["obs"]
        return anuncio_id, "actualizado", record

    conn.execute(
        "UPDATE anuncios SET last_seen_at = CURRENT_TIMESTAMP WHERE id = ?",
        (anuncio_id,),
    )
    conn.commit()
    return anuncio_id, "sin_cambios", _row_to_dict(existing)


def has_been_notified(conn: sqlite3.Connection, anuncio_id: int, perfil: str, canal: str, content_hash: str) -> bool:
    row = conn.execute(
        """SELECT 1 FROM notificaciones
           WHERE anuncio_id = ? AND perfil = ? AND canal = ? AND content_hash_notificado = ?
           LIMIT 1""",
        (anuncio_id, perfil, canal, content_hash),
    ).fetchone()
    return row is not None


def record_notification(conn: sqlite3.Connection, anuncio_id: int, perfil: str, tipo: str,
                         canal: str, content_hash: str, contenido: str, exito: bool = True) -> None:
    conn.execute(
        """INSERT INTO notificaciones
           (anuncio_id, perfil, tipo, canal, content_hash_notificado, contenido, exito)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (anuncio_id, perfil, tipo, canal, content_hash, contenido, 1 if exito else 0),
    )
    conn.commit()


def get_anuncio_by_id(conn: sqlite3.Connection, anuncio_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM anuncios WHERE id = ?", (anuncio_id,)).fetchone()
    return _row_to_dict(row) if row else None


def list_anuncios(conn: sqlite3.Connection, fuente: str | None = None) -> list[dict]:
    if fuente:
        rows = conn.execute("SELECT * FROM anuncios WHERE fuente = ? ORDER BY id", (fuente,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM anuncios ORDER BY id").fetchall()
    return [_row_to_dict(r) for r in rows]


def count_by_fuente(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("SELECT fuente, COUNT(*) as n FROM anuncios GROUP BY fuente").fetchall()
    return {r["fuente"]: r["n"] for r in rows}
