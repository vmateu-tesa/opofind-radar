import feedparser
import json
import re

with open("data/investigacion/rss_otras_oposiciones.xml", "rb") as f:
    raw = f.read()

feed = feedparser.parse(raw)

print("Bozo (error de parseo)?", feed.bozo, feed.bozo_exception if feed.bozo else "")
print("Feed title:", feed.feed.get("title"))
print("Feed link:", feed.feed.get("link"))
print("Feed description:", feed.feed.get("description"))
print("Feed language:", feed.feed.get("language"))
print(f"\nNúmero de <item>: {len(feed.entries)}")

# Ver claves disponibles en el primer entry
print("\nClaves del primer entry:", list(feed.entries[0].keys()))

print("\n=== Primeros 3 items completos ===")
for e in feed.entries[:3]:
    print(json.dumps({k: e[k] for k in e.keys() if k in ("title", "link", "description", "id", "guid", "pubdate", "published")}, ensure_ascii=False, indent=2))

# Ningún <guid> ni <pubDate>?
tiene_guid = any("id" in e or "guidislink" in e for e in feed.entries)
tiene_pubdate = any("published" in e for e in feed.entries)
print(f"\n¿Algún item tiene guid/id?: {tiene_guid}")
print(f"¿Algún item tiene pubDate/published?: {tiene_pubdate}")

# Extraer pdf id del link de cada item
pdf_ids_rss = []
for e in feed.entries:
    m = re.search(r"/(\d+)\.pdf", e.get("link", ""))
    pdf_ids_rss.append(m.group(1) if m else None)

print(f"\nIDs de PDF en RSS: {len(pdf_ids_rss)}, únicos: {len(set(pdf_ids_rss))}, con None: {pdf_ids_rss.count(None)}")

with open("data/investigacion/filas_extraidas.json", "r", encoding="utf-8") as f:
    tabla = json.load(f)

ids_tabla = set()
for r in tabla:
    m = re.search(r"/(\d+)\.pdf", r["bases_href"])
    if m:
        ids_tabla.add(m.group(1))

ids_rss = set(x for x in pdf_ids_rss if x)

print(f"\nIDs únicos en TABLA: {len(ids_tabla)}")
print(f"IDs únicos en RSS: {len(ids_rss)}")
print(f"IDs en TABLA pero NO en RSS: {len(ids_tabla - ids_rss)}")
print(f"IDs en RSS pero NO en TABLA: {len(ids_rss - ids_tabla)}")

faltantes = ids_tabla - ids_rss
if faltantes:
    print("\nMuestra de IDs que están en la tabla pero NO en el RSS (hasta 15):")
    faltantes_ordenados = sorted(faltantes, key=lambda x: int(x))
    for fid in faltantes_ordenados[:15]:
        fila = next(r for r in tabla if fid in r["bases_href"])
        print(f"  {fid}: {fila['plaza'][:40]} | {fila['entidad'][:30]} | obs={fila['obs'][:60]!r}")
    print(f"  ... total {len(faltantes)}")

# Comprobar si el RSS respeta orden: ¿está ordenado por ID descendente (más reciente primero)?
nums_rss_en_orden = [int(x) for x in pdf_ids_rss if x]
es_descendente = all(nums_rss_en_orden[i] >= nums_rss_en_orden[i+1] for i in range(len(nums_rss_en_orden)-1))
print(f"\n¿RSS viene ordenado por ID descendente (más nuevo primero)?: {es_descendente}")
print("Primeros 10 IDs en el orden del RSS:", nums_rss_en_orden[:10])
print("Últimos 10 IDs en el orden del RSS:", nums_rss_en_orden[-10:])

# Comprobar si description contiene SIEMPRE el mismo Obs que la tabla, para los que coinciden
print("\n=== Comparando descripción RSS vs Obs de tabla para IDs comunes ===")
comunes = ids_tabla & ids_rss
muestras_comparadas = 0
diferencias = 0
for e in feed.entries:
    m = re.search(r"/(\d+)\.pdf", e.get("link", ""))
    if not m:
        continue
    pid = m.group(1)
    if pid not in comunes:
        continue
    fila = next((r for r in tabla if pid in r["bases_href"]), None)
    if not fila:
        continue
    desc = e.get("description", "")
    # extraer texto tras "Observaciones:"
    obs_match = re.search(r"Observaciones:\s*(?:</strong>)?\s*(.*)", desc, re.IGNORECASE | re.DOTALL)
    obs_rss = re.sub(r"<[^>]+>", "", obs_match.group(1)).strip() if obs_match else None
    muestras_comparadas += 1
    if obs_rss != fila["obs"] and not (not obs_rss and not fila["obs"]):
        diferencias += 1
        if diferencias <= 5:
            print(f"  DIFERENCIA en ID {pid}:")
            print(f"    RSS obs: {obs_rss!r}")
            print(f"    Tabla obs: {fila['obs']!r}")

print(f"\nTotal comparadas: {muestras_comparadas}, con diferencia de Obs: {diferencias}")
