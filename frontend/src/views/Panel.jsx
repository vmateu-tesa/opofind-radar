import React, { useMemo } from 'react';
import { AlertTriangle, Clock, Bell, RefreshCw, Star, MapPin, CalendarCheck, Inbox, Zap } from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import KpiCard from '../components/KpiCard';
import ConvocatoriaRow from '../components/ConvocatoriaRow';
import Vigilancias from '../components/Vigilancias';

const MS_7_DIAS = 7 * 24 * 60 * 60 * 1000;

// Vista de inicio: KPIs clicables, columnas "cierran pronto" / "últimas
// novedades" y tira de estado del radar.
function Panel({ convocatorias, municipios, vigilancias, estadoRadar, syncing, syncMsg, onSync, onNavegar, onToggleSeguimiento, onIA }) {
  const stats = useMemo(() => {
    const ahora = Date.now();
    let abiertas = 0, cierranPronto = 0, nuevas7 = 0, seguidas = 0;
    for (const c of convocatorias) {
      if (c.plazo_estado === 'abierto' || c.plazo_estado === 'cierra_pronto') abiertas += 1;
      if (c.plazo_estado === 'cierra_pronto') cierranPronto += 1;
      if (c.seguimiento) seguidas += 1;
      const t = Date.parse(c.fecha_publicacion);
      if (!Number.isNaN(t) && ahora - t < MS_7_DIAS) nuevas7 += 1;
    }
    return { abiertas, cierranPronto, nuevas7, seguidas };
  }, [convocatorias]);

  const favoritos = municipios.filter((m) => m.favorito).length;

  const listaCierranPronto = useMemo(() =>
    convocatorias
      .filter((c) => (c.plazo_estado === 'abierto' || c.plazo_estado === 'cierra_pronto') && c.dias_restantes != null)
      .sort((a, b) => a.dias_restantes - b.dias_restantes)
      .slice(0, 8),
    [convocatorias]);

  const novedades = useMemo(() =>
    [...convocatorias]
      .sort((a, b) => Date.parse(b.fecha_publicacion) - Date.parse(a.fecha_publicacion))
      .slice(0, 8),
    [convocatorias]);

  const canales = estadoRadar?.canales || {};
  const canalesActivos = Object.entries(canales).filter(([, v]) => v).map(([k]) => k);
  const sinCanales = estadoRadar && canalesActivos.length === 0;

  let proximo = null;
  if (estadoRadar?.proxima_ejecucion) {
    try {
      proximo = format(new Date(estadoRadar.proxima_ejecucion), "EEEE d 'a las' HH:mm", { locale: es });
    } catch {
      proximo = estadoRadar.proxima_ejecucion;
    }
  }

  return (
    <div>
      <h1 className="titulo-vista">Panel</h1>
      <p className="subtitulo-vista">Radar de empleo público · provincia de Alicante</p>

      {sinCanales && (
        <div className="banner-danger">
          <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <b>Ningún canal de aviso configurado.</b> El radar detecta, pero las alertas no llegan
            a ningún sitio (tampoco las de tus municipios favoritos). Ve a la pestaña{' '}
            <a style={{ cursor: 'pointer' }} onClick={() => onNavegar('estado')}>Estado</a> para ver
            qué variables configurar en Coolify.
          </div>
        </div>
      )}

      <Vigilancias vigilancias={vigilancias} />

      <div className="kpi-grid">
        <KpiCard icono={CalendarCheck} valor={stats.abiertas} etiqueta="Plazo abierto" tono="var(--ok)"
          onClick={() => onNavegar('explorar', { plazo: 'abierto' })} />
        <KpiCard icono={Clock} valor={stats.cierranPronto} etiqueta="Cierran pronto" tono="var(--warn)"
          onClick={() => onNavegar('explorar', { plazo: 'cierra_pronto' })} />
        <KpiCard icono={Zap} valor={stats.nuevas7} etiqueta="Nuevas (7 días)" tono="var(--info)"
          onClick={() => onNavegar('explorar', { orden: 'recientes' })} />
        <KpiCard icono={Star} valor={stats.seguidas} etiqueta="En seguimiento" tono="#fbbf24"
          onClick={() => onNavegar('seguimiento')} />
        <KpiCard icono={MapPin} valor={favoritos} etiqueta="Municipios fav." tono="#fb7185"
          onClick={() => onNavegar('municipios')} />
        <KpiCard icono={Inbox} valor={convocatorias.length} etiqueta="Total registradas" tono="var(--muted)"
          onClick={() => onNavegar('explorar', {})} />
      </div>

      <div className="dos-columnas">
        <div className="glass-card">
          <div className="card-titulo"><Clock size={16} color="var(--warn)" /> Cierran pronto</div>
          {listaCierranPronto.length === 0 ? (
            <div className="estado-vacio">Ninguna convocatoria con plazo abierto ahora mismo.</div>
          ) : (
            <div className="lista-filas">
              {listaCierranPronto.map((c) => (
                <ConvocatoriaRow key={c.id} c={c} compacta onToggleSeguimiento={onToggleSeguimiento} onIA={onIA} />
              ))}
            </div>
          )}
        </div>

        <div className="glass-card">
          <div className="card-titulo"><Bell size={16} color="var(--info)" /> Últimas novedades</div>
          {novedades.length === 0 ? (
            <div className="estado-vacio">Sin datos todavía. Lanza una sincronización.</div>
          ) : (
            <div className="lista-filas">
              {novedades.map((c) => (
                <ConvocatoriaRow key={c.id} c={c} compacta onToggleSeguimiento={onToggleSeguimiento} onIA={onIA} />
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="glass-card tira-radar">
        <span className={`chip ${canales.telegram ? 'chip-ok' : 'chip-muted'}`}>Telegram {canales.telegram ? '✓' : '✗'}</span>
        <span className={`chip ${canales.whatsapp ? 'chip-ok' : 'chip-muted'}`}>WhatsApp {canales.whatsapp ? '✓' : '✗'}</span>
        <span className={`chip ${canales.email ? 'chip-ok' : 'chip-muted'}`}>Email {canales.email ? '✓' : '✗'}</span>
        {proximo && <span>Próximo escaneo: {proximo}</span>}
        <span>10 fuentes monitorizadas</span>
        <span style={{ flex: 1 }} />
        {syncMsg && <span className="chip chip-info">{syncMsg}</span>}
        <button type="button" className="btn btn-ghost" onClick={onSync} disabled={syncing}>
          <RefreshCw size={15} className={syncing ? 'spin' : ''} />
          {syncing ? 'Sincronizando...' : 'Sincronizar ahora'}
        </button>
      </div>
    </div>
  );
}

export default Panel;
