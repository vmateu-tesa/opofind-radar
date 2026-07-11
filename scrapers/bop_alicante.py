"""Scraper del Boletin Oficial de la Provincia de Alicante (BOP), categoria
"III. Administracion Local", via el endpoint AJAX interno que usa el
buscador de la sede electronica de la Diputacion de Alicante.

La pagina https://sede.diputacionalicante.es/consultas-bop/ tiene un
<form> decorativo (sin submit real). Un <script> inline dispara en su lugar
una llamada AJAX (jQuery $.getJSON) a wseConsultaAjax.php, una consulta POR
DIA CONCRETO ya filtrada server-side por tipoorganismo (4 = "III.
Administracion Local"). No hace falta sesion, CSRF token ni captcha.

Fuente SECUNDARIA: la tabla de "otras oposiciones" ya anota en su campo Obs
cuando el BOP publica algo de cada proceso ya conocido. Este scraper sirve
sobre todo para detectar avisos de empleo publico que aun no esten
reflejados alli, o para el enlace directo al PDF del BOP. El campo
`extracto` mezcla cualquier tipo de anuncio municipal, por eso se filtra por
palabras clave de empleo publico antes de dar de alta una convocatoria.
"""

import datetime as dt
import hashlib
import re

import requests
from typing import List

from scrapers.base import BaseScraper, ConvocatoriaData

CONSULTA_URL = (
    "https://sede.diputacionalicante.es/wp-content/themes/"
    "Desarrollo-Diputacion/webservices/wseConsultaAjax.php"
)

# Value del <select name="tipoorganismo"> para "III. ADMINISTRACION LOCAL".
TIPOORGANISMO_ADMIN_LOCAL = "4"

PARAM_TMPL = (
    "<raiz><entrada><registro>"
    "<fechaPub>{fecha_ddmmyyyy}</fechaPub>"
    "<tipoorganismo>{tipoorganismo}</tipoorganismo>"
    "</registro></entrada></raiz>"
)

# Filtro amplio de "esto suena a empleo publico" sobre el extracto en minusculas.
EMPLEO_PUBLICO_RE = re.compile(
    r"oferta.{0,15}empleo|"
    r"oposicion|"
    r"concurso.{0,15}oposicion|"
    r"proceso selectivo|"
    r"procesos selectivos|"
    r"convocatoria|"
    r"bolsa.{0,10}(trabajo|empleo)|"
    r"funcionari|"
    r"personal laboral|"
    r"plaza.{0,15}vacante|"
    r"provision.{0,10}plaza|"
    r"lista.{0,15}(provisional|definitiv).{0,15}admitid|"
    r"tribunal.{0,10}calificador|"
    r"bases.{0,20}(especific|general).{0,20}(convocatoria|selectiv|plaza)"
)


def _es_empleo_publico(extracto: str) -> bool:
    return bool(EMPLEO_PUBLICO_RE.search((extracto or "").lower()))


def _first(value, default: str = "") -> str:
    """Los campos del JSON vienen como listas de 1 elemento (tipico de una
    conversion XML->JSON). Indexa [0] a prueba de listas vacias/None."""
    if not value:
        return default
    if isinstance(value, list):
        return value[0] if value else default
    return value


class BopAlicanteScraper(BaseScraper):
    def __init__(self, dias_atras: int = 2):
        # Por defecto hoy + ayer (por si el cron corrio tarde). No existe
        # forma de pedir un rango de fechas en una sola llamada a este
        # endpoint: un dias_atras grande implica esa cantidad de peticiones
        # secuenciales. Usar un valor mayor solo para un backfill puntual.
        self.dias_atras = dias_atras

    def _fetch_dia(self, fecha: dt.date):
        param = PARAM_TMPL.format(
            fecha_ddmmyyyy=fecha.strftime("%d/%m/%Y"),
            tipoorganismo=TIPOORGANISMO_ADMIN_LOCAL,
        )
        params = {"nemo": "BOP_CON", "usuario": "-", "param": param}
        response = requests.get(CONSULTA_URL, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()
        # Dia sin boletin (fin de semana/festivo): HTTP 200 con {"error": ...}
        # en vez de la clave "boletin". Es comportamiento normal, no un fallo.
        if not isinstance(data, dict) or "boletin" not in data:
            return None
        return data

    def _parse_registro(self, registro: dict) -> ConvocatoriaData | None:
        extracto = _first(registro.get("extracto")).strip()
        if not extracto or not _es_empleo_publico(extracto):
            return None

        anyo = _first(registro.get("anyo")).strip()
        edicto = _first(registro.get("edicto")).strip()
        if not anyo or not edicto:
            return None

        entidad = _first(registro.get("denominacion")).strip() or _first(registro.get("ampliacion")).strip()
        n_bop = _first(registro.get("nBop")).strip()
        desecun = _first(registro.get("desecun")).strip()
        obs_parts = []
        if n_bop:
            obs_parts.append(f"BOP nº{n_bop}/{anyo}")
        if desecun:
            obs_parts.append(f"({desecun})")

        return ConvocatoriaData(
            id_origen=f"bop-{anyo}-{edicto}",
            fuente="bop_alicante",
            titulo=extracto,
            entidad=entidad,
            enlace=_first(registro.get("ubicacion")).strip(),
            fecha_inicio=_first(registro.get("fechaPublica")).strip(),
            fecha_fin="",
            observaciones=" ".join(obs_parts),
            vacantes="",
        )

    def scrape(self) -> List[ConvocatoriaData]:
        convocatorias = []
        hoy = dt.date.today()

        for delta in range(self.dias_atras):
            fecha = hoy - dt.timedelta(days=delta)
            try:
                data = self._fetch_dia(fecha)
            except Exception as e:
                print(f"Error consultando BOP del {fecha.isoformat()}: {e}")
                continue

            if data is None:
                continue

            bop_list = (data.get("boletin") or {}).get("bop") or []
            for bop in bop_list:
                for registro in bop.get("registro") or []:
                    conv = self._parse_registro(registro)
                    if conv:
                        convocatorias.append(conv)

        return convocatorias


if __name__ == "__main__":
    scraper = BopAlicanteScraper()
    resultados = scraper.scrape()
    print(f"Encontradas {len(resultados)} convocatorias de empleo publico en BOP (admin. local).")
    if resultados:
        print("Muestra de la primera:")
        print(resultados[0].model_dump_json(indent=2))
