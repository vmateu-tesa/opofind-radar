import React, { useState, useEffect } from 'react';
import { RefreshCw, X } from 'lucide-react';

// Modal de contenido generado con IA (temario o test interactivo).
// Comportamiento portado del App.jsx anterior: el test corrige al elegir
// opcion (verde la correcta, rojo la elegida si falla).
function ModalIA({ modal, cargando, onClose }) {
  const [respuestas, setRespuestas] = useState({});

  useEffect(() => {
    setRespuestas({});
  }, [modal]);

  if (!modal && !cargando) return null;

  return (
    <div className="modal-fondo" onClick={onClose}>
      <div className="modal-cuerpo" onClick={(e) => e.stopPropagation()}>
        {cargando ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <RefreshCw className="spin" size={32} style={{ margin: '0 auto 1rem' }} />
            <h3>Generando con IA...</h3>
            <p style={{ color: 'var(--text-secondary)' }}>Contenido adaptado a la convocatoria.</p>
          </div>
        ) : (
          <>
            <button
              type="button"
              className="btn-icono"
              style={{ position: 'absolute', top: '1rem', right: '1rem' }}
              onClick={onClose}
            >
              <X size={22} />
            </button>
            <h2 style={{ paddingRight: '2.5rem' }}>
              {modal.type === 'test' ? 'Test de preparación' : 'Índice de temario'}
            </h2>
            <h4 style={{ color: 'var(--text-secondary)', margin: '0.5rem 0 1.75rem' }}>{modal.title}</h4>

            {modal.type === 'temario' && (
              <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                {modal.data.temario || modal.data.error}
              </div>
            )}

            {modal.type === 'test' && modal.data.error && (
              <div className="banner-danger">
                <div>
                  {modal.data.error}
                  {modal.data.raw && (
                    <pre style={{ marginTop: '1rem', fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                      {modal.data.raw}
                    </pre>
                  )}
                </div>
              </div>
            )}

            {modal.type === 'test' && modal.data.test && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.75rem' }}>
                {modal.data.test.map((q, qi) => {
                  const contestada = respuestas[qi] !== undefined;
                  return (
                    <div key={qi} style={{ background: 'rgba(255,255,255,0.03)', padding: '1.25rem', borderRadius: 12 }}>
                      <h4 style={{ margin: '0 0 1rem', fontSize: '1.05rem' }}>{qi + 1}. {q.question}</h4>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {q.options.map((opcion, oi) => {
                          const elegida = respuestas[qi] === oi;
                          const correcta = oi === q.correct_index;
                          let fondo = 'rgba(255,255,255,0.05)';
                          let borde = '1px solid rgba(255,255,255,0.1)';
                          if (contestada && correcta) {
                            fondo = 'rgba(16,185,129,0.2)';
                            borde = '1px solid var(--ok)';
                          } else if (contestada && elegida && !correcta) {
                            fondo = 'rgba(239,68,68,0.2)';
                            borde = '1px solid var(--danger)';
                          }
                          return (
                            <div
                              key={oi}
                              onClick={() => !contestada && setRespuestas((prev) => ({ ...prev, [qi]: oi }))}
                              style={{
                                padding: '0.85rem 1rem', borderRadius: 9, background: fondo, border: borde,
                                cursor: contestada ? 'default' : 'pointer', display: 'flex', gap: '0.7rem', alignItems: 'center',
                              }}
                            >
                              <span style={{ width: 20, textAlign: 'center', fontWeight: 700 }}>
                                {contestada && correcta ? '✓' : contestada && elegida ? '×' : ''}
                              </span>
                              <span>{opcion}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default ModalIA;
