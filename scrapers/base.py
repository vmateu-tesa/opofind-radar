from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel
import hashlib

class ConvocatoriaData(BaseModel):
    id_origen: str
    fuente: str
    titulo: str
    entidad: Optional[str] = None
    enlace: Optional[str] = None
    fecha_inicio: Optional[str] = None
    fecha_fin: Optional[str] = None
    observaciones: Optional[str] = None
    vacantes: Optional[str] = None
    
    def calculate_hash(self) -> str:
        # Concatenate relevant fields to detect changes
        content = f"{self.titulo}|{self.entidad}|{self.enlace}|{self.observaciones}|{self.vacantes}|{self.fecha_inicio}|{self.fecha_fin}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

class BaseScraper(ABC):
    
    @abstractmethod
    def scrape(self) -> List[ConvocatoriaData]:
        """
        Executes the scraping logic and returns a list of ConvocatoriaData objects.
        """
        pass
