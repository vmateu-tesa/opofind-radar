from scrapling import Fetcher
from typing import List
from scrapers.base import BaseScraper, ConvocatoriaData
import hashlib

class BenidormScraper(BaseScraper):
    URL = "https://sede.benidorm.org/eAdmin/Tablon.do?action=verAnuncios&tipoTablon=1"
    
    def scrape(self) -> List[ConvocatoriaData]:
        convocatorias = []
        
        try:
            # We use Fetcher from scrapling to get the HTML
            # auto_match will handle common bypasses if needed
            fetcher = Fetcher(auto_match=True)
            page = fetcher.get(self.URL)
            
            # Look for the table or list of announcements
            # Usually Benidorm sede has a table with class 'tablaDatos' or similar
            # Since we don't have the exact HTML, we'll try a generic approach
            rows = page.css("table tr")
            
            for row in rows[1:]: # Skip header
                cols = row.css("td")
                if len(cols) >= 3:
                    # Depending on exact structure, assuming:
                    # 0: Fecha, 1: Titulo/Asunto, 2: Enlace/Detalle
                    fecha = cols[0].text
                    titulo = cols[1].text.strip()
                    
                    enlace = ""
                    enlace_tag = cols[1].css("a") or cols[2].css("a")
                    if enlace_tag:
                        enlace = enlace_tag[0].attrib.get('href', '')
                        if enlace and not enlace.startswith('http'):
                            enlace = "https://sede.benidorm.org" + enlace
                            
                    id_origen = hashlib.md5((titulo + fecha).encode('utf-8')).hexdigest()
                    
                    convocatorias.append(
                        ConvocatoriaData(
                            id_origen=id_origen,
                            fuente="benidorm",
                            titulo=titulo,
                            entidad="Ayuntamiento de Benidorm",
                            enlace=enlace,
                            observaciones=fecha,
                            vacantes=""
                        )
                    )
        except Exception as e:
            print(f"Error en scraper de Benidorm: {e}")
            
        return convocatorias

if __name__ == "__main__":
    scraper = BenidormScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} convocatorias en Benidorm.")
    if resultados:
        print("Muestra de la primera:")
        print(resultados[0].model_dump_json(indent=2))
