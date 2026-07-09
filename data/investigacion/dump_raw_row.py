from lxml import html as lhtml

with open("data/investigacion/tabla_otras_oposiciones.html", "r", encoding="utf-8") as f:
    content = f.read()

doc = lhtml.fromstring(content)
table = doc.xpath("//table[@id='DatosSalida']")[0]
thead = table.xpath(".//thead")[0]
print("=== THEAD RAW ===")
print(lhtml.tostring(thead, encoding="unicode"))

rows = table.xpath(".//tr")[1:]
print("\n=== FILA 0 RAW ===")
print(lhtml.tostring(rows[0], encoding="unicode", pretty_print=True))

print("\n=== FILA 2 (Psicólogo, con fechas) RAW ===")
print(lhtml.tostring(rows[2], encoding="unicode", pretty_print=True))

# Buscar una fila con Obs no vacío
import json
with open("data/investigacion/filas_extraidas.json", "r", encoding="utf-8") as f:
    regs = json.load(f)

con_obs = [r for r in regs if r.get("obs")]
print(f"\nFilas con Obs no vacío: {len(con_obs)}")
for r in con_obs[:5]:
    print(json.dumps(r, ensure_ascii=False, indent=2))
