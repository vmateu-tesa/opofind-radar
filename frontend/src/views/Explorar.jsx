import React, { useMemo } from 'react';
import { Search, Star, X } from 'lucide-react';
import ConvocatoriaRow from '../components/ConvocatoriaRow';
import { TIPOS, normaliza, FILTROS_DEFECTO } from '../api';

const CHIPS_PLAZO = [
  { value: 'todas', label: 'Todas' },
  { value: 'abierto', label: 'Plazo abierto' },
  { value: 'cierra_pronto', label: 'Cierra pronto' },
  { value: 'proximamente', label: 'Próximamente' },
  { value: 'cerrado', label: 'Cerrado' },
  { value: 'sin_fechas', label: 'Sin fechas' },
];

function pasaPlazo(c, plazo) {
  if (plazo === 'todas') return true;
  // "Plazo abierto" agrupa abierto + cierra_pronto (en ambos se puede
  // presentar instancia); "Cierra pronto" es solo el subconjunto urgente.
  if (plazo === 'abierto') return c.plazo_estado === 'abierto' || c.plazo_estado === 'cierra_pronto';
  return c.plazo_estado === plazo;
}

// Vista principal de exploración: búsqueda + filtros + orden sobre todas
// las convocatorias cargadas (el filtrado es 100% en cliente).
function Explorar({ convocatorias, municipios, filtros, setFiltros, onToggleSeguimiento, onIA }) {
  const municipiosConDatos = useMemo(
    () => municipios.filter((m) => m.total > 0),
    [municipios],
  );

  const fuentes = useMemo(() => {
    const s = new Set(convocatorias.map((c) => c.fuente).filter(Boolean));
    return Array.from(s).sort();
  }, [convocatorias]);

  const filtradas = useMemo(() => {
    const q = normaliza(filtros.busqueda);
    const lista = convocatorias.filter((c) => {
      if (q && !normaliza(`${c.titulo} ${c.entidad || ''}`).includes(q)) return false;
      if (filtros.tipo !== 'todas' && c.tipo !== filtros.tipo) return false;
      if (filtros.municipio !== 'todos' && c.municipio !== filtros.municipio) return false;
      if (filtros.fuente !== 'todas' && c.fuente !== filtros.fuente) return false;
      if (!pasaPlazo(c, filtros.plazo)) return false;
      if (filtros.soloSeguidas && !c.seguimiento) return false;
      return true;
    });
    if (filtros.orden === 'cierre') {
      // Cierre más próximo primero; sin fecha de fin al final.
      lista.sort((a, b) => {
        const da = a.dias_restantes ?? Infinity;
        const db = b.dias_restantes ?? Infinity;
        return da - db;
      });
    } else {
      lista.sort((a, b) => Date.parse(b.fecha_publicacion) - Date.parse(a.fecha_publicacion));
    }
    return lista;
  }, [convocatorias, filtros]);

  const hayFiltros = JSON.stringify({ ...filtros, orden: 'recientes' }) !== JSON.stringify(FILTROS_DEFECTO);

  return (
    <div>
      <h1 className="titulo-vista">Explorar</h1>
      <p className="subtitulo-vista">Todas las publicaciones detectadas por el radar, con filtros.</p>

      <div className="barra-filtros">
        <div className="barra-filtros-fila">
          <div className="buscador">
            <Search size={17} />
            <input
              type="text"
              placeholder="Buscar por plaza o entidad..."
              value={filtros.busqueda}
              onChange={(e) => setFiltros({ ...filtros, busqueda: e.target.value })}
            />
          </div>
          <select className="filter-select" value={filtros.tipo}
            onChange={(e) => setFiltros({ ...filtros, tipo: e.target.value })}>
            <option value="todas">Todos los tipos</option>
            {TIPOS.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <select className="filter-select" value={filtros.municipio}
            onChange={(e) => setFiltros({ ...filtros, municipio: e.target.value })}>
            <option value="todos">Todos los municipios</option>
            {municipiosConDatos.map((m) => (
              <option key={m.nombre} value={m.nombre}>{m.nombre} ({m.total})</option>
            ))}
          </select>
          <select className="filter-select" value={filtros.fuente}
            onChange={(e) => setFiltros({ ...filtros, fuente: e.target.value })}>
            <option value="todas">Todas las fuentes</option>
            {fuentes.map((f) => <option key={f} value={f}>{f}</option>)}
          </select>
          <select className="filter-select" value={filtros.orden}
            onChange={(e) => setFiltros({ ...filtros, orden: e.target.value })}>
            <option value="recientes">Más recientes</option>
            <option value="cierre">Cierre más próximo</option>
          </select>
        </div>

        <div className="barra-filtros-fila">
          {CHIPS_PLAZO.map((ch) => (
            <button key={ch.value} type="button"
              className={`chip-filtro ${filtros.plazo === ch.value ? 'activo' : ''}`}
              onClick={() => setFiltros({ ...filtros, plazo: ch.value })}>
              {ch.label}
            </button>
          ))}
          <label className="check-inline">
            <input type="checkbox" checked={filtros.soloSeguidas}
              onChange={(e) => setFiltros({ ...filtros, soloSeguidas: e.target.checked })} />
            <Star size={14} fill={filtros.soloSeguidas ? 'currentColor' : 'none'} />
            Solo seguidas
          </label>
          <span style={{ flex: 1 }} />
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {filtradas.length} de {convocatorias.length}
          </span>
        </div>
      </div>

      {filtradas.length === 0 ? (
        <div className="glass-card estado-vacio">
          <span>Nada coincide con estos filtros.</span>
          {hayFiltros && (
            <button type="button" className="btn btn-ghost"
              onClick={() => setFiltros({ ...FILTROS_DEFECTO })}>
              <X size={15} /> Limpiar filtros
            </button>
          )}
        </div>
      ) : (
        <div className="lista-filas">
          {filtradas.map((c) => (
            <ConvocatoriaRow key={c.id} c={c} onToggleSeguimiento={onToggleSeguimiento} onIA={onIA} />
          ))}
        </div>
      )}
    </div>
  );
}

export default Explorar;
