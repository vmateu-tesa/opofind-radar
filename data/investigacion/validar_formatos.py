import json
import re

with open("data/investigacion/filas_extraidas.json", "r", encoding="utf-8") as f:
    regs = json.load(f)

no_numericas = [r for r in regs if not re.fullmatch(r"\d+", r["vacantes"].strip())]
print("Filas con Vacantes NO puramente numerico:", len(no_numericas))
for r in no_numericas[:10]:
    print(" ", repr(r["vacantes"]), "|", r["plaza"][:40])

vacias = [r for r in regs if not r["vacantes"].strip()]
print("Vacantes vacias:", len(vacias))

raras_ini = [r for r in regs if r["f_ini"] and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", r["f_ini"])]
raras_fin = [r for r in regs if r["f_fin"] and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", r["f_fin"])]
print("f_ini con formato raro:", len(raras_ini), raras_ini[:3])
print("f_fin con formato raro:", len(raras_fin), raras_fin[:3])

raras_bases = [r for r in regs if r["bases_text"] and not re.fullmatch(r"\d{2}/\d{2}/\d{4}", r["bases_text"])]
print("bases_text (fecha del link) con formato raro:", len(raras_bases))
for r in raras_bases[:10]:
    print("  ", repr(r["bases_text"]), "|", r["plaza"][:40])

solo_ini = [r for r in regs if r["f_ini"] and not r["f_fin"]]
solo_fin = [r for r in regs if r["f_fin"] and not r["f_ini"]]
print("Solo f_ini sin f_fin:", len(solo_ini))
print("Solo f_fin sin f_ini:", len(solo_fin))
for r in solo_ini[:5]:
    print("  SOLO INI:", r["f_ini"], "|", r["plaza"][:40])
for r in solo_fin[:5]:
    print("  SOLO FIN:", r["f_fin"], "|", r["plaza"][:40])
