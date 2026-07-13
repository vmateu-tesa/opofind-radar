import React, { useState } from 'react';
import { Star, ExternalLink, Building2, MapPin, BookOpen, FileText, ChevronDown } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { es } from 'date-fns/locale';
import PlazoChip from './PlazoChip';
import { limpiarHtml, etiquetaTipo } from '../api';

// Fila densa y expandible de convocatoria. Se usa en Explorar, Seguimiento
// y (en modo compacto) en las columnas del Panel. El click en la fila abre
// el detalle; la estrella y el enlace externo no propagan el click.
function ConvocatoriaRow({ c, onToggleSeguimiento, onIA, compacta = false }) {
  const [expandida, setExpandida] = useState(false);

  let publicada = '';
  try {
    publicada = formatDistanceToNow(new Date(c.fecha_publicacion), { addSuffix: true, locale: es });
  } catch {
    publicada = '';
  }
  const obs = limpiarHtml(c.observaciones);

  return (
    <div className={`fila ${expandida ? 'expandida' : ''} ${compacta ? 'fila-compacta' : ''}`}>
      <div className="fila-principal" onClick={() => setExpandida(!expandida)}>
        <button
          type="button"
          className={`btn-icono ${c.seguimiento ? 'activo' : ''}`}
          title={c.seguimiento ? 'Dejar de seguir' : 'Seguir (avisa de cualquier novedad)'}
          onClick={(e) => { e.stopPropagation(); onToggleSeguimiento(c.id, c.seguimiento); }}
        >
          <Star size={17} fill={c.seguimiento ? 'currentColor' : 'none'} />
        </button>

        <div className="fila-cuerpo">
          <div className="fila-titulo">{c.titulo}</div>
          <div className="fila-meta">
            <span className="fila-meta-item"><Building2 size={13} />{c.entidad || 'Sin entidad'}</span>
            {c.municipio && (
              <span className="chip chip-municipio"><MapPin size={11} />{c.municipio}</span>
            )}
            {!compacta && c.tipo && <span className="badge badge-tipo">{etiquetaTipo(c.tipo)}</span>}
            {!compacta && c.estado === 'nuevo' && <span className="badge badge-nuevo">Nuevo</span>}
            {!compacta && c.estado === 'actualizado' && <span className="badge badge-actualizado">Actualizado</span>}
          </div>
        </div>

        <div className="fila-derecha">
          <PlazoChip estado={c.plazo_estado} dias={c.dias_restantes} fechaInicio={c.fecha_inicio} />
          {!compacta && publicada && <span className="fila-fecha">{publicada}</span>}
          <span className="fila-chevron"><ChevronDown size={16} /></span>
        </div>
      </div>

      {expandida && (
        <div className="fila-detalle">
          <div className="fila-detalle-datos">
            <span><b>Fuente:</b> {c.fuente}</span>
            {(c.fecha_inicio || c.fecha_fin) && (
              <span><b>Plazo:</b> {c.fecha_inicio || '?'} — {c.fecha_fin || '?'}</span>
            )}
            {c.vacantes && <span><b>Vacantes:</b> {c.vacantes}</span>}
            {c.tipo && <span><b>Tipo:</b> {etiquetaTipo(c.tipo)}</span>}
          </div>

          {obs && <div className="fila-observaciones">{obs}</div>}

          <div className="fila-acciones">
            {c.enlace && (
              <a href={c.enlace} target="_blank" rel="noreferrer" className="btn btn-ghost">
                <ExternalLink size={15} /> Ver bases / anuncio
              </a>
            )}
            {/* Temario y Test con IA solo para procesos selectivos abiertos
                (tipo === 'convocatoria'): una lista de admitidos o un
                nombramiento no tiene temario que estudiar. */}
            {c.tipo === 'convocatoria' && (
              <>
                <button type="button" className="btn btn-primary" onClick={() => onIA(c, 'temario')}>
                  <BookOpen size={15} /> Temario IA
                </button>
                <button type="button" className="btn btn-warn" onClick={() => onIA(c, 'test')}>
                  <FileText size={15} /> Test IA
                </button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ConvocatoriaRow;
