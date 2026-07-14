import React from 'react';
import { Crosshair, ExternalLink, CheckCircle2, Radar } from 'lucide-react';
import PlazoChip from './PlazoChip';

// Vigilancias dirigidas: plazas fijas que el cron busca cada día. Se muestran
// destacadas porque son "lo más importante" para el usuario: en cuanto una de
// estas plazas se convoca, quiere enterarse el primero.
function Vigilancias({ vigilancias }) {
  if (!vigilancias || vigilancias.length === 0) return null;

  return (
    <div className="glass-card vigilancia-panel" style={{ marginBottom: '1.5rem' }}>
      <div className="card-titulo">
        <Crosshair size={16} color="#fb7185" /> Vigilancia especial
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {vigilancias.map((v) => {
          const detectada = v.estado === 'detectada';
          return (
            <div key={v.slug} className={`vigilancia ${detectada ? 'detectada' : ''}`}>
              <div className="vigilancia-cabecera">
                <div className="vigilancia-titulo">
                  {detectada ? <CheckCircle2 size={16} color="var(--ok)" /> : <Radar size={16} color="var(--warn)" />}
                  {v.titulo}
                </div>
                {detectada
                  ? <span className="chip chip-ok">¡HA SALIDO!</span>
                  : <span className="chip chip-warn">Vigilando</span>}
              </div>

              {v.notas && <div className="vigilancia-notas">{v.notas}</div>}

              <div className="vigilancia-acciones">
                {detectada && v.convocatoria ? (
                  <>
                    <PlazoChip
                      estado={v.convocatoria.plazo_estado}
                      dias={v.convocatoria.dias_restantes}
                      fechaInicio={v.convocatoria.fecha_inicio}
                    />
                    {v.convocatoria.enlace && (
                      <a href={v.convocatoria.enlace} target="_blank" rel="noreferrer" className="btn btn-primary">
                        <ExternalLink size={14} /> Ver convocatoria
                      </a>
                    )}
                  </>
                ) : (
                  <span className="vigilancia-estado-texto">
                    Aún no se ha convocado. El radar la busca cada día a las 04:00 y te avisará en cuanto salga.
                  </span>
                )}
                {v.enlace && (
                  <a href={v.enlace} target="_blank" rel="noreferrer" className="btn btn-ghost">
                    <ExternalLink size={14} /> Documento de referencia (RPT)
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default Vigilancias;
