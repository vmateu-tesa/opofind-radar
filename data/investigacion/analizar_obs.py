import json

with open("data/investigacion/filas_extraidas.json", "r", encoding="utf-8") as f:
    regs = json.load(f)

con_obs = [r for r in regs if r.get("obs")]
sin_obs = [r for r in regs if not r.get("obs")]
print(f"Filas con Obs no vacío: {len(con_obs)} / {len(regs)}")
print(f"Filas con Obs vacío: {len(sin_obs)} / {len(regs)}")

# Ejemplos con Obs concatenado (varios eventos: DOGV + BOP + BOE etc)
multi_evento = [r for r in con_obs if r["obs"].count("publica") + r["obs"].count("Publica") > 1]
print(f"\nFilas con Obs con VARIOS eventos concatenados (heurística 'publica'x2+): {len(multi_evento)}")
for r in multi_evento[:5]:
    print(" -", r["plaza"][:40], "|", r["entidad"][:35])
    print("   OBS:", r["obs"])

# ver distribución de longitud de obs
import statistics
longitudes = [len(r["obs"]) for r in con_obs]
print(f"\nLongitud Obs: min={min(longitudes)} max={max(longitudes)} media={statistics.mean(longitudes):.1f}")

# Buscar filas con f_ini/f_fin vacíos pero obs con "abre plazo" (contradicción?)
print("\n--- Muestras variadas de Obs (10 aleatorias-ish, cada 15) ---")
for r in con_obs[::15][:10]:
    print(" -", r["obs"])

# Comprobar entidades únicas y si hay más que ayuntamientos (mancomunidades, consorcios, etc)
entidades = sorted(set(r["entidad"] for r in regs))
print(f"\nEntidades únicas: {len(entidades)}")
no_ayto = [e for e in entidades if "yuntamiento" not in e]
print(f"Entidades que NO son 'Ayuntamiento de...': {len(no_ayto)}")
for e in no_ayto:
    print("  -", e)

# ids de pdf: comprobar unicidad
import re
pdf_ids = []
for r in regs:
    m = re.search(r"/(\d+)\.pdf", r["bases_href"])
    pdf_ids.append(m.group(1) if m else None)
print(f"\nTotal IDs de PDF extraídos: {len(pdf_ids)}, únicos: {len(set(pdf_ids))}")
if len(pdf_ids) != len(set(pdf_ids)):
    from collections import Counter
    c = Counter(pdf_ids)
    dup = {k: v for k, v in c.items() if v > 1}
    print("IDs duplicados:", dup)
    for pid in dup:
        print(f"\n  Filas con PDF ID {pid}:")
        for r in regs:
            if pid in r["bases_href"]:
                print("   ", r["plaza"], "|", r["entidad"], "|", r["obs"][:80])

# rango de IDs numéricos (para ver si son correlativos / orden cronológico)
nums = sorted(int(p) for p in pdf_ids if p)
print(f"\nRango IDs numéricos: {nums[0]} - {nums[-1]}")
