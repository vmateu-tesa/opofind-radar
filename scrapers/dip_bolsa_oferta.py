import feedparser
from typing import List
from scrapers.base import BaseScraper, ConvocatoriaData
import hashlib

class DipBolsaOfertaScraper(BaseScraper):
    URLS = {
        "dip_bolsa": "https://sede.diputacionalicante.es/rssbolsa/",
        "dip_oferta": "https://sede.diputacionalicante.es/rssoferta/"
    }
    
    def scrape(self) -> List[ConvocatoriaData]:
        convocatorias = []
        
        for fuente_id, url in self.URLS.items():
            feed = feedparser.parse(url)
            
            for entry in feed.entries:
                titulo = entry.get('title', 'Sin título')
                enlace = entry.get('link', '')
                observaciones = entry.get('description', '')
                
                # Para RSS, usamos el guid (id) del feed si está presente, o un hash del enlace
                id_origen = entry.get('id', '')
                if not id_origen:
                    id_origen = hashlib.md5(enlace.encode('utf-8')).hexdigest() if enlace else hashlib.md5(titulo.encode('utf-8')).hexdigest()
                    
                convocatorias.append(
                    ConvocatoriaData(
                        id_origen=id_origen,
                        fuente=fuente_id,
                        titulo=titulo,
                        entidad="Diputación de Alicante", # Asumimos esto para estos RSS específicos
                        enlace=enlace,
                        observaciones=observaciones,
                        vacantes=""
                    )
                )
                
        return convocatorias

if __name__ == "__main__":
    scraper = DipBolsaOfertaScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} convocatorias en bolsa y oferta.")
    if resultados:
        print("Muestra de la primera:")
        print(resultados[0].model_dump_json(indent=2))
