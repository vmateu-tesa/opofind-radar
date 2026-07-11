"""Clasificador heuristico de 'tipo de publicacion' para una convocatoria.

Categorias (en orden de prioridad -- si el texto encaja en varias, gana la
mas especifica/avanzada en el ciclo de vida del proceso):

  1. "nombramiento"  -- resultado final: nombramiento de funcionario de
                         carrera, toma de posesion.
  2. "listas"         -- listas de admitidos/excluidos, aprobados,
                         resultados de ejercicios, tribunal calificador.
  3. "convocatoria"   -- apertura de un proceso: bases, oferta de empleo
                         publico, proceso selectivo, bolsa de trabajo.
  4. "otros"          -- cualquier cosa que no encaje claramente arriba
                         (rectificaciones sueltas, ampliaciones de plazo
                         sin mas contexto, anuncios genericos...).

Es deliberadamente simple (regex sobre texto en minusculas): no pretende
ser perfecto, sirve para poder filtrar en la interfaz. El usuario siempre
puede abrir el enlace a las bases/BOP/BOE para ver el detalle real.
"""

import re

_NOMBRAMIENTO_RE = re.compile(
    r"nombramiento|"
    r"funcionari[oa]s?\s+de\s+carrera|"
    r"toma\s+de\s+posesion"
)

_LISTAS_RE = re.compile(
    r"lista\s+(provisional|definitiv)|"
    r"admitid|"
    r"exclu[iy]d|"
    r"aprobad|"
    r"tribunal\s+calificador|"
    r"resultado\s+(del?\s+)?(ejercicio|proceso)|"
    r"designaci[oó]n\s+(del?\s+)?tribunal"
)

TIPOS_VALIDOS = ("nombramiento", "listas", "convocatoria", "otros")


def classify_tipo(titulo: str, observaciones: str = "") -> str:
    """Devuelve una de TIPOS_VALIDOS a partir del titulo (y opcionalmente
    las observaciones) de una convocatoria.

    "convocatoria" es el valor por defecto (no "otros"): la inmensa mayoria
    de filas de fuentes como dip_otras_oposiciones son directamente el
    nombre de la plaza ("Psicologo", "Agente de Igualdad"...) sin ninguna
    palabra clave reconocible -- pero estar en esas tablas YA significa que
    es un proceso de seleccion abierto/en curso. "otros" queda solo como
    red de seguridad para texto vacio."""
    texto = f"{titulo or ''} {observaciones or ''}".lower()
    if not texto.strip():
        return "otros"

    if _NOMBRAMIENTO_RE.search(texto):
        return "nombramiento"
    if _LISTAS_RE.search(texto):
        return "listas"
    return "convocatoria"
