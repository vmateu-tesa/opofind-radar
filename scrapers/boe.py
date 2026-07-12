import os
import time
import requests
from typing import List
from datetime import datetime, timedelta
from scrapers.base import BaseScraper, ConvocatoriaData
from core.geo import es_alicante

# Ventana de dias hacia atras que se raspan del BOE en cada ejecucion.
# Por defecto 1 mes (el usuario lo pidio): asi, aunque el cron falle varios
# dias o se despliegue de cero, no se pierde ninguna convocatoria reciente.
# Configurable via env BOE_DIAS_ATRAS. Cada dia es 1 peticion a la API del
# BOE (con ~1s de espera entre ellas), asi que 30 dias = ~30s.
_DIAS_ATRAS_DEFAULT = 30


class BoeScraper(BaseScraper):
    BASE_URL = "https://www.boe.es/datosabiertos/api/boe/sumario/"

    def __init__(self, date_str: str = None, dias_atras: int = None):
        """
        :param date_str: 'YYYYMMDD' para raspar UN dia concreto (tests /
            uso puntual). Si se da, se ignora dias_atras.
        :param dias_atras: numero de dias hacia atras a raspar (incluido hoy).
            Default: env BOE_DIAS_ATRAS o 30.
        """
        self.date_str = date_str
        if dias_atras is None:
            try:
                dias_atras = int(os.getenv("BOE_DIAS_ATRAS", str(_DIAS_ATRAS_DEFAULT)))
            except ValueError:
                dias_atras = _DIAS_ATRAS_DEFAULT
        self.dias_atras = max(1, dias_atras)

    def _fetch_dia(self, date_str: str) -> List[ConvocatoriaData]:
        url = f"{self.BASE_URL}{date_str}"
        headers = {"Accept": "application/json"}
        try:
            response = requests.get(url, headers=headers, timeout=20)
            # 404 = dia sin boletin (domingos/festivos): normal, no es error.
            if response.status_code == 404:
                return []
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching BOE for {date_str}: {e}")
            return []
        return self._parse_sumario(data)

    def _parse_sumario(self, data: dict) -> List[ConvocatoriaData]:
        convocatorias = []
        try:
            diarios = data.get("data", {}).get("sumario", {}).get("diario", [])
            if not isinstance(diarios, list):
                diarios = [diarios]

            for diario in diarios:
                secciones = diario.get("seccion", [])
                if not isinstance(secciones, list):
                    secciones = [secciones]

                for seccion in secciones:
                    # Solo "II.B Oposiciones y concursos" (codigo "2B"). La
                    # "II.A Nombramientos, situaciones e incidencias" son
                    # movimientos individuales, no procesos selectivos.
                    nombre_sec = seccion.get("nombre", "")
                    codigo_sec = seccion.get("codigo", "")
                    if codigo_sec == "2B" or "Oposiciones y concursos" in nombre_sec:
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

                                # Solo la provincia de Alicante: el BOE es
                                # nacional y trae convocatorias de toda España.
                                # La entidad del BOE suele ser generica
                                # (p.ej. 'ADMINISTRACION LOCAL'), asi que el
                                # municipio va tipicamente en el titulo.
                                if not es_alicante(entidad_nombre, titulo):
                                    continue

                                url_pdf = ""
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
                                        vacantes="",
                                    )
                                )
        except Exception as e:
            print(f"Error parsing BOE JSON: {e}")
        return convocatorias

    def scrape(self) -> List[ConvocatoriaData]:
        # Modo un-solo-dia (tests / uso puntual).
        if self.date_str:
            return self._fetch_dia(self.date_str)

        # Modo ventana: raspa los ultimos `dias_atras` dias. Deduplica por
        # id_origen (una convocatoria aparece un unico dia, pero por si acaso).
        vistos = set()
        resultado = []
        hoy = datetime.now().date()
        for delta in range(self.dias_atras):
            dia = hoy - timedelta(days=delta)
            for conv in self._fetch_dia(dia.strftime("%Y%m%d")):
                if conv.id_origen in vistos:
                    continue
                vistos.add(conv.id_origen)
                resultado.append(conv)
            time.sleep(1)  # cortesia con la API del BOE (~1 req/s)
        return resultado


if __name__ == "__main__":
    scraper = BoeScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} convocatorias en BOE (Alicante, ultimos {scraper.dias_atras} dias).")
    for c in resultados[:8]:
        print(f"  - {c.entidad[:30]:30} | {c.titulo[:70]}")
