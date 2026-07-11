import hashlib
import requests
from bs4 import BeautifulSoup
from typing import List
from scrapers.base import BaseScraper, ConvocatoriaData
import re

class DipOtrasOposicionesScraper(BaseScraper):
    URL = "https://sede.diputacionalicante.es/empleo-otras-oposiciones/"

    def scrape(self) -> List[ConvocatoriaData]:
        response = requests.get(self.URL, timeout=20)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        convocatorias = []
        
        # Find the main table. Usually it's the one with class or just the largest one.
        # Let's target all tables and find the one that has our headers.
        table = None
        for t in soup.find_all('table'):
            text = t.get_text()
            if 'Plaza' in text and 'Entidad' in text and 'Bases' in text:
                table = t
                break
                
        if not table:
            return []
            
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
        
        # Skip header if it's in tr. Comprobamos por celda <th> real o por
        # texto EXACTO "Plaza" (no substring): una convocatoria real puede
        # perfectamente titularse "2 Plazas de Bombero" y no debe descartarse.
        for row in rows:
            cols = row.find_all(['td', 'th'])
            if not cols or row.find('th') or cols[0].get_text(strip=True) == 'Plaza':
                continue
                
            # Columns: Plaza | Entidad | Vacantes | Bases | Presentación F.Inicio | Presentación F.Final | Obs
            if len(cols) >= 7:
                plaza = cols[0].get_text(strip=True)
                entidad = cols[1].get_text(strip=True)
                vacantes = cols[2].get_text(strip=True)
                
                bases_link = cols[3].find('a')
                enlace = bases_link['href'] if bases_link and 'href' in bases_link.attrs else ""
                if enlace and not enlace.startswith('http'):
                    enlace = "https://sede.diputacionalicante.es" + enlace
                    
                fecha_inicio = cols[4].get_text(strip=True)
                fecha_fin = cols[5].get_text(strip=True)

                # La celda "Obs" no lleva texto plano: cada publicacion
                # posterior (BOP/DOGV/BOE) se representa como un <img> cuyo
                # atributo title/alt lleva el aviso real, p.ej.
                # <img title="DOGV.- 24/04/2026 - Publica extracto bases.">
                # Puede haber mas de uno si se acumulan varias publicaciones;
                # se concatenan en orden. Se incluye tambien el texto plano
                # de la celda por si en algun caso viniera asi directamente.
                obs_imgs = [
                    (img.get('title') or img.get('alt') or '').strip()
                    for img in cols[6].find_all('img')
                ]
                obs_texto = cols[6].get_text(strip=True)
                obs_partes = [o for o in obs_imgs if o] + ([obs_texto] if obs_texto else [])
                obs = " | ".join(obs_partes)
                
                # Extract ID from PDF filename, e.g. 11357.pdf
                id_match = re.search(r'/([^/]+)\.pdf', enlace, re.IGNORECASE)
                if id_match:
                    id_origen = id_match.group(1)
                else:
                    # Fallback to a hash of the URL or row if no ID found
                    id_origen = hashlib.md5(enlace.encode('utf-8')).hexdigest() if enlace else hashlib.md5(plaza.encode('utf-8')).hexdigest()
                    
                convocatorias.append(
                    ConvocatoriaData(
                        id_origen=id_origen,
                        fuente="dip_otras_oposiciones",
                        titulo=plaza,
                        entidad=entidad,
                        enlace=enlace,
                        fecha_inicio=fecha_inicio,
                        fecha_fin=fecha_fin,
                        observaciones=obs,
                        vacantes=vacantes
                    )
                )
                
        return convocatorias

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    scraper = DipOtrasOposicionesScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} convocatorias.")
    if resultados:
        print("Muestra de la primera:")
        print(resultados[0].model_dump_json(indent=2))
