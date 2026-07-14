import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import { api, FILTROS_DEFECTO } from './api';
import Sidebar from './components/Sidebar';
import ModalIA from './components/ModalIA';
import Panel from './views/Panel';
import Explorar from './views/Explorar';
import Seguimiento from './views/Seguimiento';
import Municipios from './views/Municipios';
import Estado from './views/Estado';

const CLAVE_UI = 'oporadar.ui';
const VISTAS = ['panel', 'explorar', 'seguimiento', 'municipios', 'estado'];

// Estado de interfaz persistido (vista activa + filtros de Explorar).
// Tolerante a basura en localStorage: si no parsea, se ignora.
function cargarUI() {
  try {
    const crudo = JSON.parse(localStorage.getItem(CLAVE_UI));
    if (crudo && typeof crudo === 'object') return crudo;
  } catch {
    // JSON corrupto: empezamos de cero
  }
  return {};
}

function App() {
  const ui = useMemo(cargarUI, []);

  const [convocatorias, setConvocatorias] = useState([]);
  const [municipios, setMunicipios] = useState([]);
  const [vigilancias, setVigilancias] = useState([]);
  const [estadoRadar, setEstadoRadar] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState(null);

  const [vista, setVista] = useState(VISTAS.includes(ui.vista) ? ui.vista : 'panel');
  const [filtros, setFiltros] = useState({ ...FILTROS_DEFECTO, ...(ui.filtros || {}) });

  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState(null);

  // Modal IA (temario / test).
  const [modalIA, setModalIA] = useState(null);
  const [modalCargando, setModalCargando] = useState(false);

  const cargar = useCallback(async () => {
    setErrorCarga(null);
    try {
      const [convs, est, munis, vigs] = await Promise.all([
        api.convocatorias(),
        api.estado(),
        api.municipios(),
        api.vigilancias(),
      ]);
      setConvocatorias(convs);
      setEstadoRadar(est);
      setMunicipios(munis);
      setVigilancias(vigs);
    } catch (err) {
      console.error('Error cargando datos', err);
      setErrorCarga(err.message || 'No se pudo conectar con el backend');
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  // Persistir vista y filtros.
  useEffect(() => {
    try {
      localStorage.setItem(CLAVE_UI, JSON.stringify({ vista, filtros }));
    } catch {
      // almacenamiento lleno o bloqueado: no es critico
    }
  }, [vista, filtros]);

  // Navegación: cambiar de vista y, opcionalmente, preconfigurar los
  // filtros de Explorar (lo usan los KPIs del Panel).
  const navegar = useCallback((nuevaVista, filtrosParciales) => {
    if (filtrosParciales) {
      setFiltros({ ...FILTROS_DEFECTO, ...filtrosParciales });
    }
    setVista(nuevaVista);
    window.scrollTo({ top: 0 });
  }, []);

  const toggleSeguimiento = useCallback(async (id, seguidaActualmente) => {
    // Optimista: cambia ya el estado local y revierte si la llamada falla.
    setConvocatorias((prev) => prev.map((c) => (c.id === id ? { ...c, seguimiento: !seguidaActualmente } : c)));
    try {
      await (seguidaActualmente ? api.dejarDeSeguir(id) : api.seguir(id));
    } catch (err) {
      console.error('Error al cambiar seguimiento', err);
      setConvocatorias((prev) => prev.map((c) => (c.id === id ? { ...c, seguimiento: seguidaActualmente } : c)));
    }
  }, []);

  const toggleFavorito = useCallback(async (nombre, esFavorito) => {
    setMunicipios((prev) => prev.map((m) => (m.nombre === nombre ? { ...m, favorito: !esFavorito } : m)));
    try {
      await (esFavorito ? api.delFavorito(nombre) : api.addFavorito(nombre));
    } catch (err) {
      console.error('Error al cambiar municipio favorito', err);
      setMunicipios((prev) => prev.map((m) => (m.nombre === nombre ? { ...m, favorito: esFavorito } : m)));
    }
  }, []);

  const handleSync = useCallback(async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      await api.triggerSync();
      setSyncMsg('Escaneando fuentes...');
      // El scrape corre en segundo plano en el backend; recargamos al rato.
      setTimeout(async () => {
        await cargar();
        setSyncing(false);
        setSyncMsg(null);
      }, 6000);
    } catch (err) {
      // P. ej. el rate-limit de 5 min devuelve 429 con un mensaje claro.
      setSyncMsg(err.message);
      setSyncing(false);
    }
  }, [cargar]);

  const handleIA = useCallback(async (c, tipo) => {
    if (c.tipo !== 'convocatoria') return; // regla dura: solo procesos selectivos
    setModalIA(null);
    setModalCargando(true);
    try {
      const data = tipo === 'test' ? await api.generarTest(c.id) : await api.generarTemario(c.id);
      setModalIA({ type: tipo, data, title: c.titulo });
    } catch (err) {
      setModalIA({ type: tipo, data: { error: err.message || 'Error al contactar con la IA' }, title: c.titulo });
    } finally {
      setModalCargando(false);
    }
  }, []);

  const contadores = useMemo(() => ({
    explorar: convocatorias.length,
    seguimiento: convocatorias.filter((c) => c.seguimiento).length,
    municipios: municipios.filter((m) => m.favorito).length,
  }), [convocatorias, municipios]);

  const sinCanales = Boolean(
    estadoRadar && Object.values(estadoRadar.canales || {}).every((v) => !v),
  );

  let contenido;
  if (cargando) {
    contenido = (
      <div className="pantalla-carga">
        <RefreshCw className="spin" size={30} />
        <span>Cargando el radar...</span>
      </div>
    );
  } else if (errorCarga) {
    contenido = (
      <div className="pantalla-carga">
        <AlertTriangle size={30} color="var(--danger)" />
        <span>No se pudieron cargar los datos: {errorCarga}</span>
        <button type="button" className="btn btn-primary" onClick={() => { setCargando(true); cargar(); }}>
          <RefreshCw size={15} /> Reintentar
        </button>
      </div>
    );
  } else if (vista === 'explorar') {
    contenido = (
      <Explorar convocatorias={convocatorias} municipios={municipios}
        filtros={filtros} setFiltros={setFiltros}
        onToggleSeguimiento={toggleSeguimiento} onIA={handleIA} />
    );
  } else if (vista === 'seguimiento') {
    contenido = (
      <Seguimiento convocatorias={convocatorias}
        onToggleSeguimiento={toggleSeguimiento} onIA={handleIA} onNavegar={navegar} />
    );
  } else if (vista === 'municipios') {
    contenido = (
      <Municipios municipios={municipios} convocatorias={convocatorias}
        onToggleFavorito={toggleFavorito} onToggleSeguimiento={toggleSeguimiento} onIA={handleIA}
        sinCanales={sinCanales} />
    );
  } else if (vista === 'estado') {
    contenido = (
      <Estado estadoRadar={estadoRadar} syncing={syncing} syncMsg={syncMsg} onSync={handleSync} />
    );
  } else {
    contenido = (
      <Panel convocatorias={convocatorias} municipios={municipios} vigilancias={vigilancias}
        estadoRadar={estadoRadar} syncing={syncing} syncMsg={syncMsg} onSync={handleSync}
        onNavegar={navegar} onToggleSeguimiento={toggleSeguimiento} onIA={handleIA} />
    );
  }

  return (
    <div className="app-shell">
      <Sidebar vista={vista} onNavegar={navegar} contadores={contadores} estadoRadar={estadoRadar} />
      <main className="app-main">{contenido}</main>
      <ModalIA modal={modalIA} cargando={modalCargando} onClose={() => setModalIA(null)} />
    </div>
  );
}

export default App;
