"""Extrae y analiza todas las filas de datos de la tabla DatosSalida."""
import re
import json
from lxml import html as lhtml

with open("data/investigacion/tabla_otras_oposiciones.html", "r", encoding="utf-8") as f:
    content = f.read()

doc = lhtml.fromstring(content)
table = doc.xpath("//table[@id='DatosSalida']")[0]

# Buscar thead/tbody
thead = table.xpath(".//thead")
tbody = table.xpath(".//tbody")
print("¿Tiene <thead>?", bool(thead), " ¿Tiene <tbody>?", bool(tbody))

if tbody:
    rows = tbody[0].xpath(".//tr")
else:
    rows = table.xpath(".//tr")[1:]  # saltar cabecera

print(f"Filas de datos (excluyendo cabecera): {len(rows)}")

registros = []
for tr in rows:
    tds = tr.xpath(".//td")
    if len(tds) < 7:
        # fila rara, capturar para inspección
        registros.append({"RAW_TDS": len(tds), "html": lhtml.tostring(tr, encoding="unicode")[:500]})
        continue
    plaza = tds[0].text_content().strip()
    entidad = tds[1].text_content().strip()
    vacantes = tds[2].text_content().strip()
    # columna Bases: buscar <a href=...>
    bases_links = tds[3].xpath(".//a/@href")
    bases_text = tds[3].text_content().strip()
    f_ini = tds[4].text_content().strip()
    f_fin = tds[5].text_content().strip()
    obs_img_title = tds[6].xpath(".//img/@title")
    obs_img_alt = tds[6].xpath(".//img/@alt")
    obs_text_directo = tds[6].text_content().strip()
    obs = obs_img_title[0] if obs_img_title else (obs_img_alt[0] if obs_img_alt else obs_text_directo)
    registros.append({
        "plaza": plaza,
        "entidad": entidad,
        "vacantes": vacantes,
        "bases_href": bases_links[0] if bases_links else None,
        "bases_text": bases_text,
        "bases_num_links": len(bases_links),
        "f_ini": f_ini,
        "f_fin": f_fin,
        "obs": obs,
        "obs_tiene_img": bool(obs_img_title or obs_img_alt),
        "obs_title_vs_alt_iguales": (obs_img_title == obs_img_alt) if (obs_img_title and obs_img_alt) else None,
    })

print(f"\nTotal registros parseados: {len(registros)}")

# Mostrar 3 filas de muestra completas
print("\n=== MUESTRA: primeras 3 filas ===")
for r in registros[:3]:
    print(json.dumps(r, ensure_ascii=False, indent=2))

print("\n=== MUESTRA: últimas 3 filas ===")
for r in registros[-3:]:
    print(json.dumps(r, ensure_ascii=False, indent=2))

# Analizar patrón de enlaces de Bases
sin_link = [r for r in registros if isinstance(r, dict) and r.get("bases_href") is None]
print(f"\nFilas SIN enlace de Bases: {len(sin_link)}")
for r in sin_link[:10]:
    print(" ", r)

con_link = [r for r in registros if isinstance(r, dict) and r.get("bases_href")]
print(f"\nFilas CON enlace de Bases: {len(con_link)}")

# Comprobar cuántos terminan en /NNNN.pdf
pdf_pattern = re.compile(r"/(\d+)\.pdf(?:$|[?#])", re.IGNORECASE)
con_pdf_numerico = [r for r in con_link if pdf_pattern.search(r["bases_href"])]
sin_pdf_numerico = [r for r in con_link if not pdf_pattern.search(r["bases_href"])]
print(f"  -> con nombre numérico .pdf: {len(con_pdf_numerico)}")
print(f"  -> SIN nombre numérico .pdf (excepciones): {len(sin_pdf_numerico)}")
for r in sin_pdf_numerico[:20]:
    print("   EXCEPCION:", r["bases_href"], "| plaza:", r["plaza"][:60])

# Múltiples links en la misma celda Bases?
multi = [r for r in con_link if r["bases_num_links"] > 1]
print(f"\nFilas con MÁS de 1 enlace en celda Bases: {len(multi)}")
for r in multi[:10]:
    print("  ", r["bases_href"], r["plaza"][:60])

# Filas con TDS != 7 (raras)
raras = [r for r in registros if "RAW_TDS" in r]
print(f"\nFilas con estructura de columnas distinta a 7: {len(raras)}")
for r in raras[:5]:
    print(r)

# Guardar todo en JSON para referencia
with open("data/investigacion/filas_extraidas.json", "w", encoding="utf-8") as f:
    json.dump(registros, f, ensure_ascii=False, indent=2)
print("\nGuardado en data/investigacion/filas_extraidas.json")
