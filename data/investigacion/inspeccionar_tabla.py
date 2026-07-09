"""Inspección real del HTML de https://sede.diputacionalicante.es/empleo-otras-oposiciones/"""
from lxml import html as lhtml

with open("data/investigacion/tabla_otras_oposiciones.html", "r", encoding="utf-8") as f:
    content = f.read()

print("Longitud HTML:", len(content))

doc = lhtml.fromstring(content)

tables = doc.xpath("//table")
print(f"\nNúmero de <table> en el documento: {len(tables)}")

for i, t in enumerate(tables):
    rows = t.xpath(".//tr")
    classes = t.get("class")
    tid = t.get("id")
    print(f"\n--- Tabla #{i}: id={tid!r} class={classes!r} filas(tr)={len(rows)} ---")
    if rows:
        # cabecera
        header_cells = rows[0].xpath(".//th | .//td")
        print("Cabecera:", [c.text_content().strip() for c in header_cells])

# Buscar contenedores típicos de datatables/wordpress table plugins
for attr in ["id", "class"]:
    pass

print("\n--- Buscando indicios de JS/paginación (datatables, wp-table, ajax) ---")
import re
indicios = ["DataTable", "datatable", "wp-table", "wpDataTable", "ajax", "tablepress", "TablePress", "paginate", "pagination"]
for ind in indicios:
    count = content.count(ind)
    if count:
        print(f"  '{ind}': {count} ocurrencias")

# Buscar scripts
scripts = doc.xpath("//script/@src")
print(f"\nNúmero de <script src=...>: {len(scripts)}")
for s in scripts:
    if "table" in s.lower() or "datatable" in s.lower():
        print("  script relevante:", s)
