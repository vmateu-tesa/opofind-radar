"""Motor de plazos de OpoRadar.

Este modulo es el corazon del rediseño: dado el par de fechas (inicio/fin
del plazo de instancias) de una convocatoria, calcula en que estado esta el
plazo HOY y que avisos tocan enviar. Todas las funciones son puras (la fecha
"hoy" es inyectable) para poder testearlas de forma determinista.

Caso de uso que motiva todo esto (el usuario perdio esta oferta por no
enterarse a tiempo): Bolsa de Ingeniero/a de Telecomunicaciones A1 del
Ayuntamiento de Elche, bases publicadas en el BOP de Alicante el 16/06/2026,
plazo de instancias del 17/06/2026 al 01/07/2026. La app debe garantizar que
eso no se repita: detectar la apertura pronto y recordar el cierre antes de
que sea tarde.

Convenciones:

- Las fechas llegan de los scrapers como string 'dd/mm/yyyy' (formato real
  de las fuentes: Diputacion de Alicante, BOP...). Muchas filas las traen
  vacias, asi que todo tolera None/''.
- ``dias_restantes`` cuenta los dias de hoy a fecha_fin SIN incluir hoy:
  0 significa "hoy es el ultimo dia", negativo que el plazo ya paso.
- "Quedan N dias" en el sentido coloquial (los dias en los que aun se puede
  presentar instancia, contando hoy) es ``dias_restantes + 1``. El estado
  'cierra_pronto' usa esa cuenta: quedan <= DIAS_CIERRA_PRONTO dias.
"""

import os
import re
from datetime import date

# Estados posibles de un plazo.
PROXIMAMENTE = "proximamente"    # el plazo aun no ha empezado
ABIERTO = "abierto"              # se puede presentar instancia
CIERRA_PRONTO = "cierra_pronto"  # abierto, pero quedan pocos dias
CERRADO = "cerrado"              # el plazo ya paso
SIN_FECHAS = "sin_fechas"        # la fuente no dio ninguna fecha parseable

ESTADOS_VALIDOS = (PROXIMAMENTE, ABIERTO, CIERRA_PRONTO, CERRADO, SIN_FECHAS)

# Tipos de aviso.
AVISO_APERTURA = "apertura"                      # el plazo acaba de abrirse
_AVISO_CIERRE_FMT = "cierre_{n}d"                # quedan <= n dias para el cierre

# Un plazo abierto pasa a 'cierra_pronto' cuando quedan <= 5 dias para
# presentar instancia (contando hoy: el ultimo dia incluido sigue siendo
# 'cierra_pronto', no 'cerrado').
DIAS_CIERRA_PRONTO = 5

# Umbrales de aviso de cierre por defecto (dias restantes): se avisa cuando
# quedan 5 dias y de nuevo cuando queda 1. Configurable via env
# DIAS_AVISO_CIERRE (formato '5,1').
_UMBRALES_DEFAULT = (5, 1)

# 'dd/mm/yyyy' con tolerancia: espacios alrededor, dia/mes sin cero a la
# izquierda y separadores '/', '-' o '.'. El año debe tener 4 cifras (un
# '17/06/26' es ambiguo y preferimos descartarlo a adivinar el siglo).
_FECHA_RE = re.compile(r"^\s*(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4})\s*$")


def parse_fecha(s):
    """Parsea una fecha 'dd/mm/yyyy' (formato real de las fuentes) a
    ``datetime.date``. Tolera espacios, separadores '-' o '.', y dia/mes de
    una cifra. Devuelve None si el valor esta vacio, es None o no es una
    fecha valida (p.ej. '32/13/2026' o un año de 2 cifras)."""
    if isinstance(s, date):
        # Defensivo: si alguien ya nos pasa un date, lo devolvemos tal cual.
        return s
    if not s or not isinstance(s, str):
        return None
    m = _FECHA_RE.match(s)
    if not m:
        return None
    dia, mes, anyo = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return date(anyo, mes, dia)
    except ValueError:
        return None


def dias_restantes(fecha_fin, hoy=None):
    """Dias que faltan de ``hoy`` a ``fecha_fin`` (string 'dd/mm/yyyy'),
    sin contar hoy: 0 = hoy es el ultimo dia, negativo = plazo pasado.
    None si la fecha de fin no es parseable."""
    fin = parse_fecha(fecha_fin)
    if fin is None:
        return None
    if hoy is None:
        hoy = date.today()
    return (fin - hoy).days


def estado_plazo(fecha_inicio, fecha_fin, hoy=None):
    """Estado del plazo de una convocatoria HOY. Devuelve uno de
    ESTADOS_VALIDOS:

    - 'sin_fechas':    ninguna de las dos fechas es parseable.
    - 'proximamente':  el inicio es futuro.
    - 'cerrado':       hoy > fin.
    - 'cierra_pronto': abierto y quedan <= DIAS_CIERRA_PRONTO dias contando
                       hoy (el ultimo dia del plazo incluido).
    - 'abierto':       inicio <= hoy <= fin; tambien si solo hay fin y
                       hoy <= fin, o si solo hay inicio y hoy >= inicio.
    """
    if hoy is None:
        hoy = date.today()
    inicio = parse_fecha(fecha_inicio)
    fin = parse_fecha(fecha_fin)

    if inicio is None and fin is None:
        return SIN_FECHAS
    if inicio is not None and hoy < inicio:
        return PROXIMAMENTE
    if fin is not None:
        if hoy > fin:
            return CERRADO
        # Quedan pocos dias: cuenta coloquial incluyendo hoy.
        if (fin - hoy).days + 1 <= DIAS_CIERRA_PRONTO:
            return CIERRA_PRONTO
    return ABIERTO


def leer_umbrales(valor=None):
    """Umbrales (en dias restantes) para los avisos de cierre, leidos de la
    variable de entorno DIAS_AVISO_CIERRE (formato '5,1', default '5,1').

    Parseo robusto: tolera espacios, separadores ';', duplicados y trozos
    invalidos (se ignoran). Si tras limpiar no queda nada valido, se vuelve
    al default. Devuelve la lista ordenada de mayor a menor.

    ``valor`` permite inyectar el string directamente en tests sin tocar el
    entorno."""
    if valor is None:
        valor = os.getenv("DIAS_AVISO_CIERRE") or ""
    umbrales = []
    for trozo in re.split(r"[,;\s]+", str(valor).strip()):
        if not trozo:
            continue
        try:
            n = int(trozo)
        except ValueError:
            continue
        if n >= 0 and n not in umbrales:
            umbrales.append(n)
    if not umbrales:
        umbrales = list(_UMBRALES_DEFAULT)
    return sorted(umbrales, reverse=True)


def _valor(conv, clave):
    """Extrae un campo de una convocatoria, sea dict (claves) u objeto
    (atributos, p.ej. el modelo SQLAlchemy Convocatoria)."""
    if isinstance(conv, dict):
        return conv.get(clave)
    return getattr(conv, clave, None)


def avisos_pendientes(conv, avisos_ya_enviados, umbrales=None, hoy=None):
    """Tipos de aviso que tocan HOY para una convocatoria.

    ``conv`` es un dict (u objeto) con claves fecha_inicio/fecha_fin;
    ``avisos_ya_enviados`` es el set de tipos de aviso ya enviados para esa
    convocatoria; ``umbrales`` son los dias de antelacion para los avisos de
    cierre (default: leer_umbrales()).

    Tipos posibles:

    - 'apertura':     el plazo esta abierto (o cierra pronto) y nunca se ha
                      avisado de la apertura.
    - 'cierre_{N}d':  quedan como mucho N dias (0 <= dias_restantes <= N).
                      Solo se emite el umbral MAS PEQUEÑO aplicable hoy, y
                      solo si no se ha enviado ya: asi nunca salen cierre_5d
                      y cierre_1d el mismo dia, y si ya se aviso de lo mas
                      urgente no se repite con algo menos urgente.

    Sin fechas parseables (o plazo futuro/cerrado) devuelve [].
    """
    if hoy is None:
        hoy = date.today()
    if umbrales is None:
        umbrales = leer_umbrales()

    fecha_inicio = _valor(conv, "fecha_inicio")
    fecha_fin = _valor(conv, "fecha_fin")
    estado = estado_plazo(fecha_inicio, fecha_fin, hoy)
    if estado not in (ABIERTO, CIERRA_PRONTO):
        return []

    avisos = []
    if AVISO_APERTURA not in avisos_ya_enviados:
        avisos.append(AVISO_APERTURA)

    dias = dias_restantes(fecha_fin, hoy)
    if dias is not None and dias >= 0:
        aplicables = sorted(n for n in umbrales if dias <= n)
        if aplicables:
            aviso_cierre = _AVISO_CIERRE_FMT.format(n=aplicables[0])
            if aviso_cierre not in avisos_ya_enviados:
                avisos.append(aviso_cierre)

    return avisos
