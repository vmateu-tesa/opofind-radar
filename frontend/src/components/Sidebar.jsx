import React from 'react';
import { Radar, Home, Search, Star, MapPin, Settings } from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';

const ITEMS = [
  { id: 'panel', etiqueta: 'Panel', Icono: Home },
  { id: 'explorar', etiqueta: 'Explorar', Icono: Search },
  { id: 'seguimiento', etiqueta: 'Seguimiento', Icono: Star },
  { id: 'municipios', etiqueta: 'Municipios', Icono: MapPin },
  { id: 'estado', etiqueta: 'Estado', Icono: Settings },
];

function Sidebar({ vista, onNavegar, contadores, estadoRadar }) {
  let proximo = null;
  if (estadoRadar?.proxima_ejecucion) {
    try {
      proximo = format(new Date(estadoRadar.proxima_ejecucion), "d MMM · HH:mm", { locale: es });
    } catch {
      proximo = null;
    }
  }
  const canales = estadoRadar
    ? Object.values(estadoRadar.canales || {}).filter(Boolean).length
    : 0;

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <span className="sidebar-logo-icono"><Radar size={26} /></span>
        <span className="sidebar-logo-texto">OpoRadar</span>
      </div>
      <nav className="sidebar-nav">
        {ITEMS.map(({ id, etiqueta, Icono }) => (
          <button
            key={id}
            type="button"
            className={`nav-item ${vista === id ? 'activo' : ''}`}
            onClick={() => onNavegar(id)}
          >
            <Icono size={18} />
            <span className="nav-item-etiqueta">{etiqueta}</span>
            {contadores[id] != null && contadores[id] > 0 && (
              <span className="nav-item-contador">{contadores[id]}</span>
            )}
          </button>
        ))}
      </nav>
      <div className="sidebar-pie">
        {proximo && <div>Próximo escaneo: {proximo}</div>}
        <div>{canales > 0 ? `${canales} canal${canales > 1 ? 'es' : ''} de aviso activo${canales > 1 ? 's' : ''}` : 'Sin canales de aviso'}</div>
      </div>
    </aside>
  );
}

export default Sidebar;
