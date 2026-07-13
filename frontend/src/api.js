// Cliente minimo de la API de OpoRadar. Rutas relativas: en produccion
// nginx proxya /api al backend y en desarrollo lo hace vite.config.js.

async function json(res) {
  if (!res.ok) {
    let detalle = '';
    try {
      const cuerpo = await res.json();
      detalle = cuerpo.detail || cuerpo.error || '';
    } catch {
      // cuerpo no JSON: nos quedamos con el codigo
    }
    throw new Error(detalle || `Error ${res.status}`);
  }
  return res.json();
}

export const api = {
  convocatorias: () => fetch('/api/convocatorias').then(json),
  estado: () => fetch('/api/estado').then(json),
  municipios: () => fetch('/api/municipios').then(json),
  seguir: (id) => fetch(`/api/convocatorias/${id}/seguir`, { method: 'POST' }).then(json),
  dejarDeSeguir: (id) => fetch(`/api/convocatorias/${id}/dejar-de-seguir`, { method: 'POST' }).then(json),
  addFavorito: (nombre) => fetch('/api/municipios-favoritos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nombre }),
  }).then(json),
  delFavorito: (nombre) => fetch(`/api/municipios-favoritos/${encodeURIComponent(nombre)}`, { method: 'DELETE' }).then(json),
  triggerSync: () => fetch('/api/trigger-sync', { method: 'POST' }).then(json),
  generarTemario: (id) => fetch(`/api/generar-estudio/${id}`, { method: 'POST' }).then(json),
  generarTest: (id) => fetch(`/api/generar-test/${id}`, { method: 'POST' }).then(json),
};

// Convierte el HTML que puede venir en observaciones (texto scrapeado de
// webs y RSS de terceros) a texto plano: <br> pasa a salto de linea y el
// resto de etiquetas desaparece. NUNCA se inyecta HTML de las fuentes en el
// DOM (nada de dangerouslySetInnerHTML).
export function limpiarHtml(texto) {
  if (!texto) return '';
  const sinBr = String(texto).replace(/<br\s*\/?>/gi, '\n');
  const doc = new DOMParser().parseFromString(sinBr, 'text/html');
  return (doc.body.textContent || '').trim();
}

// Normaliza para busquedas: minusculas y sin acentos ("Dénia" -> "denia").
export function normaliza(texto) {
  return (texto || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

// Filtros por defecto de la vista Explorar (tambien los presets de los
// KPIs del Panel parten de aqui).
export const FILTROS_DEFECTO = {
  busqueda: '',
  tipo: 'todas',
  municipio: 'todos',
  fuente: 'todas',
  plazo: 'todas',
  soloSeguidas: false,
  orden: 'recientes',
};

export const TIPOS = [
  { value: 'convocatoria', label: 'Convocatoria' },
  { value: 'listas', label: 'Listas admitidos/aprobados' },
  { value: 'nombramiento', label: 'Nombramiento' },
  { value: 'otros', label: 'Otros' },
];

export function etiquetaTipo(tipo) {
  return TIPOS.find((t) => t.value === tipo)?.label || tipo || '';
}

// Las 10 fuentes que rastrea el cron diario (solo informativo, vista Estado).
export const FUENTES = [
  { nombre: 'Diputación de Alicante · Otras oposiciones', cubre: 'Anuncios de otras administraciones de la provincia' },
  { nombre: 'Diputación de Alicante · Bolsas y oferta', cubre: 'Bolsas de trabajo y oferta de empleo público' },
  { nombre: 'BOE', cubre: 'Sección 2B, provincia de Alicante, últimos 30 días' },
  { nombre: 'BOP de Alicante', cubre: 'Boletín Oficial de la Provincia' },
  { nombre: 'DOGV', cubre: 'Diari Oficial de la GVA, filtrado a la provincia' },
  { nombre: 'Ayuntamiento de Benidorm', cubre: 'Tablón de empleo público' },
  { nombre: 'Ayuntamiento de Elche', cubre: 'Tablón de Recursos Humanos' },
  { nombre: 'Gestiona · Marina Baixa', cubre: 'Tablones de 9 ayuntamientos (Altea, La Nucía, Polop...)' },
  { nombre: "L'Alfàs del Pi", cubre: 'Tablón de selección de personal' },
  { nombre: 'Villajoyosa', cubre: 'Ofertas de empleo municipales' },
];
