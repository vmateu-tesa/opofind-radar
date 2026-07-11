import React, { useState, useEffect, useMemo } from 'react';
import { Search, RefreshCw, BookOpen, ExternalLink, Building2, Calendar, FileText, X, Star } from 'lucide-react';
import { format, isAfter, isBefore, parse } from 'date-fns';
import { es } from 'date-fns/locale';

const TIPOS = [
  { value: 'convocatoria', label: 'Convocatoria' },
  { value: 'listas', label: 'Listas admitidos/aprobados' },
  { value: 'nombramiento', label: 'Nombramiento' },
  { value: 'otros', label: 'Otros' },
];

function App() {
  const [convocatorias, setConvocatorias] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState("todas");
  const [entidadFilter, setEntidadFilter] = useState("todas");
  const [tipoFilter, setTipoFilter] = useState("todas");
  const [soloSeguidas, setSoloSeguidas] = useState(false);

  // Modal state
  const [modalData, setModalData] = useState(null); // { type: 'test' | 'temario', data: any, title: string }
  const [modalLoading, setModalLoading] = useState(false);
  const [testAnswers, setTestAnswers] = useState({}); // { questionIndex: selectedOptionIndex }

  const fetchConvocatorias = async () => {
    try {
      const res = await fetch(`/api/convocatorias`);
      const data = await res.json();
      setConvocatorias(data);
    } catch (err) {
      console.error("Error fetching data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConvocatorias();
  }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch(`/api/trigger-sync`, { method: "POST" });
      setTimeout(() => {
        fetchConvocatorias();
        setSyncing(false);
      }, 2500);
    } catch (err) {
      console.error(err);
      setSyncing(false);
    }
  };

  const handleStudy = async (id, titulo, type) => {
    setModalData(null);
    setTestAnswers({});
    setModalLoading(true);
    try {
      const endpoint = type === 'test' ? `/api/generar-test/${id}` : `/api/generar-estudio/${id}`;
      const res = await fetch(`${endpoint}`, { method: 'POST' });
      const data = await res.json();
      setModalData({ type, data, title: titulo });
    } catch (err) {
      alert("Error al contactar con la IA");
    } finally {
      setModalLoading(false);
    }
  };

  const handleAnswerSelect = (qIndex, oIndex) => {
    setTestAnswers(prev => ({ ...prev, [qIndex]: oIndex }));
  };

  const handleToggleSeguimiento = async (id, seguidaActualmente) => {
    // Actualizacion optimista: cambia el estado local ya, y si la llamada
    // falla, se revierte.
    setConvocatorias(prev => prev.map(c => c.id === id ? { ...c, seguimiento: !seguidaActualmente } : c));
    try {
      const endpoint = seguidaActualmente
        ? `/api/convocatorias/${id}/dejar-de-seguir`
        : `/api/convocatorias/${id}/seguir`;
      const res = await fetch(endpoint, { method: 'POST' });
      if (!res.ok) throw new Error('fallo la peticion');
    } catch (err) {
      console.error('Error al cambiar seguimiento', err);
      setConvocatorias(prev => prev.map(c => c.id === id ? { ...c, seguimiento: seguidaActualmente } : c));
    }
  };

  // Clasificador de estado
  const getClassifiedStatus = (c) => {
    if (!c.fecha_inicio || !c.fecha_fin) return "no_convocadas";
    try {
      const inicio = parse(c.fecha_inicio, 'dd/MM/yyyy', new Date());
      const fin = parse(c.fecha_fin, 'dd/MM/yyyy', new Date());
      const hoy = new Date();
      if (isBefore(hoy, inicio)) return "no_convocadas";
      if (isAfter(hoy, fin)) return "pasadas";
      return "en_curso";
    } catch (e) {
      return "no_convocadas";
    }
  };

  const processedData = convocatorias.map(c => ({
    ...c,
    status_radar: getClassifiedStatus(c)
  }));

  const entidadesUnicas = useMemo(() => {
    const set = new Set(convocatorias.map(c => c.entidad).filter(Boolean));
    return Array.from(set).sort((a, b) => a.localeCompare(b, 'es'));
  }, [convocatorias]);

  const filteredData = processedData.filter(c => {
    const matchesSearch = c.titulo.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          (c.entidad && c.entidad.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesTab = activeTab === "todas" || c.status_radar === activeTab;
    const matchesEntidad = entidadFilter === "todas" || c.entidad === entidadFilter;
    const matchesTipo = tipoFilter === "todas" || c.tipo === tipoFilter;
    const matchesSeguimiento = !soloSeguidas || c.seguimiento;

    return matchesSearch && matchesTab && matchesEntidad && matchesTipo && matchesSeguimiento;
  });

  return (
    <div className="animate-fade-in" style={{ position: 'relative' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <div>
          <h1 style={{ background: 'linear-gradient(to right, #f43f5e, #f59e0b)' }}>RADAR</h1>
          <p style={{ color: 'var(--text-secondary)' }}>Rastreador Avanzado de Empleo (Informática, Ingeniería y Docencia)</p>
        </div>
        <button className="btn-primary" onClick={handleSync} disabled={syncing}>
          <RefreshCw className={syncing ? "spin" : ""} size={18} />
          {syncing ? 'Sincronizando...' : 'Sincronizar'}
        </button>
      </header>

      {/* TABS */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
        <button className={`tab-btn ${activeTab === 'todas' ? 'active' : ''}`} onClick={() => setActiveTab('todas')}>
          Todas
        </button>
        <button className={`tab-btn ${activeTab === 'en_curso' ? 'active' : ''}`} onClick={() => setActiveTab('en_curso')}>
          🟢 En Curso
        </button>
        <button className={`tab-btn ${activeTab === 'no_convocadas' ? 'active' : ''}`} onClick={() => setActiveTab('no_convocadas')}>
          🟡 Aún no convocadas
        </button>
        <button className={`tab-btn ${activeTab === 'pasadas' ? 'active' : ''}`} onClick={() => setActiveTab('pasadas')}>
          🔴 Pasadas
        </button>
      </div>

      <div className="glass-card" style={{ marginBottom: '1rem', padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
        <Search size={20} color="var(--text-secondary)" />
        <input
          type="text"
          placeholder="Buscar por plaza o entidad..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'white',
            width: '100%',
            fontSize: '1rem',
            outline: 'none'
          }}
        />
      </div>

      {/* FILTROS: entidad, tipo de publicacion, solo seguidas */}
      <div className="glass-card" style={{ marginBottom: '2rem', padding: '1rem', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '1rem' }}>
        <select
          className="filter-select"
          value={entidadFilter}
          onChange={(e) => setEntidadFilter(e.target.value)}
        >
          <option value="todas">Todos los ayuntamientos/entidades</option>
          {entidadesUnicas.map(ent => (
            <option key={ent} value={ent}>{ent}</option>
          ))}
        </select>

        <select
          className="filter-select"
          value={tipoFilter}
          onChange={(e) => setTipoFilter(e.target.value)}
        >
          <option value="todas">Todos los tipos de publicación</option>
          {TIPOS.map(t => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          <input
            type="checkbox"
            checked={soloSeguidas}
            onChange={(e) => setSoloSeguidas(e.target.checked)}
          />
          <Star size={16} fill={soloSeguidas ? 'currentColor' : 'none'} />
          Solo seguidas
        </label>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>Cargando datos en el RADAR...</div>
      ) : (
        <div className="dashboard-grid">
          {filteredData.map(c => (
            <div key={c.id} className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <span className={`badge ${c.estado === 'nuevo' ? 'badge-nuevo' : 'badge-actualizado'}`}>
                    {c.estado.toUpperCase()}
                  </span>
                  {c.tipo && <span className="badge badge-tipo">{TIPOS.find(t => t.value === c.tipo)?.label || c.tipo}</span>}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  {c.status_radar === 'en_curso' && <span title="En Curso" style={{color: '#10b981'}}>🟢</span>}
                  {c.status_radar === 'no_convocadas' && <span title="Bases publicadas, sin plazo aún" style={{color: '#fbbf24'}}>🟡</span>}
                  {c.status_radar === 'pasadas' && <span title="Plazo cerrado" style={{color: '#ef4444'}}>🔴</span>}
                  <button
                    onClick={() => handleToggleSeguimiento(c.id, c.seguimiento)}
                    title={c.seguimiento ? 'Dejar de seguir' : 'Seguir esta convocatoria (avisa de cualquier novedad)'}
                    style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: c.seguimiento ? '#f59e0b' : 'var(--text-secondary)', padding: 0, display: 'flex' }}
                  >
                    <Star size={20} fill={c.seguimiento ? 'currentColor' : 'none'} />
                  </button>
                </div>
              </div>

              <h3 style={{ margin: 0, fontSize: '1.2rem', lineHeight: '1.4' }}>{c.titulo}</h3>
              
              <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Building2 size={16} />
                  <span>{c.entidad || "Sin entidad"}</span>
                </div>
                
                {(c.fecha_inicio || c.fecha_fin) && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Calendar size={16} />
                    <span>Plazo: {c.fecha_inicio || '?'} al {c.fecha_fin || '?'}</span>
                  </div>
                )}
                
                {c.vacantes && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Vacantes:</span> {c.vacantes}
                  </div>
                )}
              </div>

              {c.observaciones && (
                <div style={{ 
                  background: 'rgba(0,0,0,0.2)', 
                  padding: '0.75rem', 
                  borderRadius: '8px', 
                  fontSize: '0.85rem',
                  color: 'var(--text-secondary)',
                  marginTop: 'auto'
                }}>
                  <div dangerouslySetInnerHTML={{ __html: c.observaciones }} />
                </div>
              )}

              {/* Temario y Test con IA solo tienen sentido para un proceso
                  selectivo abierto (tipo === 'convocatoria'): una lista de
                  admitidos o un nombramiento no tiene temario que estudiar. */}
              {(c.enlace || c.tipo === 'convocatoria') && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: c.observaciones ? '1rem' : 'auto' }}>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {c.enlace && (
                      <a href={c.enlace} target="_blank" rel="noreferrer" className="btn-primary" style={{ flex: 1, justifyContent: 'center', textDecoration: 'none', background: 'rgba(255,255,255,0.1)' }}>
                        <ExternalLink size={16} /> Bases
                      </a>
                    )}
                    {c.tipo === 'convocatoria' && (
                      <button className="btn-primary" onClick={() => handleStudy(c.id, c.titulo, 'temario')} style={{ flex: 1, justifyContent: 'center', background: 'var(--accent-primary)' }}>
                        <BookOpen size={16} /> Temario
                      </button>
                    )}
                  </div>
                  {c.tipo === 'convocatoria' && (
                    <button className="btn-primary" onClick={() => handleStudy(c.id, c.titulo, 'test')} style={{ width: '100%', justifyContent: 'center', background: '#f59e0b', color: '#000' }}>
                      <FileText size={16} /> Generar Test con IA
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
          {filteredData.length === 0 && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
              No hay convocatorias en este estado.
            </div>
          )}
        </div>
      )}

      {/* Modal for AI Content */}
      {(modalData || modalLoading) && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(4px)',
          display: 'flex', justifyContent: 'center', alignItems: 'center',
          zIndex: 1000, padding: '1rem'
        }}>
          <div className="glass-card" style={{ width: '100%', maxWidth: '800px', maxHeight: '90vh', overflowY: 'auto', position: 'relative' }}>
            {modalLoading ? (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-primary)' }}>
                <RefreshCw className="spin" size={32} style={{ margin: '0 auto 1rem' }} />
                <h3>Gemini AI está pensando...</h3>
                <p style={{ color: 'var(--text-secondary)' }}>Generando contenido adaptado a la convocatoria.</p>
              </div>
            ) : (
              <>
                <button 
                  onClick={() => setModalData(null)} 
                  style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'transparent', border: 'none', color: 'white', cursor: 'pointer' }}
                >
                  <X size={24} />
                </button>
                <h2 style={{ paddingRight: '2rem' }}>{modalData.type === 'test' ? 'Test de Preparación' : 'Índice de Temario'}</h2>
                <h4 style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>{modalData.title}</h4>
                
                {modalData.type === 'temario' && (
                  <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                    {modalData.data.temario}
                  </div>
                )}

                {modalData.type === 'test' && modalData.data.error && (
                  <div style={{ color: '#ef4444', background: 'rgba(239, 68, 68, 0.1)', padding: '1rem', borderRadius: '8px' }}>
                    {modalData.data.error}
                    {modalData.data.raw && (
                      <pre style={{ marginTop: '1rem', fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
                        {modalData.data.raw}
                      </pre>
                    )}
                  </div>
                )}

                {modalData.type === 'test' && modalData.data.test && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                    {modalData.data.test.map((q, qIndex) => (
                      <div key={qIndex} style={{ background: 'rgba(255,255,255,0.03)', padding: '1.5rem', borderRadius: '12px' }}>
                        <h4 style={{ margin: '0 0 1rem 0', fontSize: '1.1rem' }}>{qIndex + 1}. {q.question}</h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {q.options.map((opt, oIndex) => {
                            const isSelected = testAnswers[qIndex] === oIndex;
                            const isAnswered = testAnswers[qIndex] !== undefined;
                            const isCorrect = oIndex === q.correct_index;
                            
                            let bg = 'rgba(255,255,255,0.05)';
                            let border = '1px solid rgba(255,255,255,0.1)';
                            
                            if (isAnswered) {
                              if (isCorrect) {
                                bg = 'rgba(16, 185, 129, 0.2)'; // green
                                border = '1px solid #10b981';
                              } else if (isSelected && !isCorrect) {
                                bg = 'rgba(239, 68, 68, 0.2)'; // red
                                border = '1px solid #ef4444';
                              }
                            } else if (isSelected) {
                              bg = 'var(--accent-primary)';
                            }

                            return (
                              <div 
                                key={oIndex}
                                onClick={() => !isAnswered && handleAnswerSelect(qIndex, oIndex)}
                                style={{
                                  padding: '1rem',
                                  borderRadius: '8px',
                                  background: bg,
                                  border: border,
                                  cursor: isAnswered ? 'default' : 'pointer',
                                  transition: 'all 0.2s',
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: '0.75rem'
                                }}
                              >
                                <div style={{ 
                                  width: '24px', height: '24px', borderRadius: '50%', 
                                  border: isAnswered && isCorrect ? '2px solid #10b981' : '2px solid rgba(255,255,255,0.3)',
                                  display: 'flex', justifyContent: 'center', alignItems: 'center',
                                  background: isSelected && !isAnswered ? 'white' : 'transparent'
                                }}>
                                  {isAnswered && isCorrect && <span style={{ color: '#10b981', fontSize: '14px' }}>✓</span>}
                                  {isAnswered && isSelected && !isCorrect && <span style={{ color: '#ef4444', fontSize: '14px' }}>×</span>}
                                </div>
                                <span>{opt}</span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
      
      <style>{`
        .spin { animation: spin 1s linear infinite; }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .tab-btn {
          background: rgba(255,255,255,0.05);
          border: 1px solid rgba(255,255,255,0.1);
          color: var(--text-secondary);
          padding: 0.5rem 1rem;
          border-radius: 99px;
          cursor: pointer;
          font-weight: 600;
          transition: all 0.2s;
          white-space: nowrap;
        }
        .tab-btn:hover { background: rgba(255,255,255,0.1); }
        .tab-btn.active {
          background: var(--accent-primary);
          color: white;
          border-color: var(--accent-primary);
        }
      `}</style>
    </div>
  );
}

export default App;
