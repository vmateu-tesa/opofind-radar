import requests
from typing import List
from datetime import datetime
from scrapers.base import BaseScraper, ConvocatoriaData
import re

class BoeScraper(BaseScraper):
    BASE_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/"
    
    def __init__(self, date_str: str = None):
        """
        :param date_str: YYYYMMDD string. Defaults to today.
        """
        if not date_str:
            self.date_str = datetime.now().strftime("%Y%m%d")
        else:
            self.date_str = date_str
            
    def scrape(self) -> List[ConvocatoriaData]:
        url = f"{self.BASE_URL}{self.date_str}"
        headers = {"Accept": "application/json"}
        
        try:
            response = requests.get(url, headers=headers, timeout=20)
            # BOE API returns 404 for days without a bulletin (Sundays, holidays)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching BOE for {self.date_str}: {e}")
            return []
            
        convocatorias = []
        
        # Navigate the JSON response to find Section II
        try:
            diarios = data.get("data", {}).get("sumario", {}).get("diario", [])
            if not isinstance(diarios, list):
                diarios = [diarios]
                
            for diario in diarios:
                secciones = diario.get("seccion", [])
                if not isinstance(secciones, list):
                    secciones = [secciones]
                    
                for seccion in secciones:
                    # Look for Section II (Autoridades y personal)
                    nombre_sec = seccion.get("nombre", "")
                    codigo_sec = seccion.get("codigo", "")
                    if "Autoridades y personal" in nombre_sec or codigo_sec.startswith("2"):
                        departamentos = seccion.get("departamento", [])
                        if not isinstance(departamentos, list):
                            departamentos = [departamentos]
                            
                        for dep in departamentos:
                            entidad_nombre = dep.get("nombre", "")
                            
                            articulos = dep.get("item", [])
                            if not isinstance(articulos, list):
                                articulos = [articulos]
                            
                            epigrafes = dep.get("epigrafe", [])
                            if not isinstance(epigrafes, list):
                                epigrafes = [epigrafes]
                                
                            for epi in epigrafes:
                                epi_arts = epi.get("item", [])
                                if not isinstance(epi_arts, list):
                                    epi_arts = [epi_arts]
                                articulos.extend(epi_arts)
                                
                            for art in articulos:
                                titulo = art.get("titulo", "")
                                id_boe = art.get("identificador", "")
                                url_pdf = ""
                                    
                                # url_pdf extract
                                pdf_data = art.get("url_pdf", {})
                                if isinstance(pdf_data, dict):
                                    url_pdf = pdf_data.get("texto", "")
                                elif isinstance(pdf_data, str):
                                    url_pdf = pdf_data
                                    
                                if url_pdf and not url_pdf.startswith("http"):
                                    url_pdf = "https://www.boe.es" + url_pdf
                                    
                                convocatorias.append(
                                    ConvocatoriaData(
                                        id_origen=id_boe,
                                        fuente="boe",
                                        titulo=titulo,
                                        entidad=entidad_nombre,
                                        enlace=url_pdf,
                                        observaciones="",
                                        vacantes=""
                                    )
                                )
        except Exception as e:
            print(f"Error parsing BOE JSON: {e}")
            
        return convocatorias

if __name__ == "__main__":
    # Test with a known weekday if today happens to be Sunday/holiday
    # Let's try today first
    scraper = BoeScraper()
    resultados = scraper.scrape()
    
    if not resultados:
         print("No se encontraron resultados hoy. Probando con 20231016 (lunes)...")
         scraper = BoeScraper("20231016")
         resultados = scraper.scrape()
         
    print(f"Encontradas {len(resultados)} convocatorias en BOE.")
    if resultados:
        print("Muestra de la primera:")
        print(resultados[0].model_dump_json(indent=2))
