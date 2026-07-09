from typing import List
from scrapers.base import BaseScraper, ConvocatoriaData

class DogvScraper(BaseScraper):
    # TODO: Implementar búsqueda de DOGV cuando se tenga URL estable.
    def scrape(self) -> List[ConvocatoriaData]:
        return []

if __name__ == "__main__":
    scraper = DogvScraper()
    print("DOGV scraper: no implementado todavía debido a URLs cambiantes.")
