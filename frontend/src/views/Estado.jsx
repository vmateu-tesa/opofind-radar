import React from 'react';
import { Send, Mail, MessageCircle, RefreshCw, CheckCircle, XCircle, Clock } from 'lucide-react';
import { format } from 'date-fns';
import { es } from 'date-fns/locale';
import { FUENTES } from '../api';

const CANALES = [
  {
    clave: 'telegram', nombre: 'Telegram', Icono: Send,
    envs: ['ENABLE_TELEGRAM=1', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'],
  },
  {
    clave: 'whatsapp', nombre: 'WhatsApp', Icono: MessageCircle,
    envs: ['ENABLE_WHATSAPP=1', 'WHATSAPP_TOKEN', 'WHATSAPP_PHONE_ID'],
  },
  {
    clave: 'email', nombre: 'Email', Icono: Mail,
    envs: ['ENABLE_EMAIL=1', 'SMTP_HOST', 'SMTP_USER', 'SMTP_PASS', 'EMAIL_TO'],
  },
];

// Estado del radar: canales de aviso, cron y fuentes monitorizadas.
function Estado({ estadoRadar, syncing, syncMsg, onSync }) {
  const canales = estadoRadar?.canales || {};

  let proximo = null;
  if (estadoRadar?.proxima_ejecucion) {
    try {
      proximo = format(new Date(estadoRadar.proxima_ejecucion), "EEEE d 'de' MMMM 'a las' HH:mm", { locale: es });
    } catch {
      proximo = estadoRadar.proxima_ejecucion;
    }
  }

  return (
    <div>
      <h1 className="titulo-vista">Estado del radar</h1>
      <p className="subtitulo-vista">
        Canales de aviso, programación del escaneo diario y fuentes monitorizadas.
      </p>

      <div className="grid-canales">
        {CANALES.map(({ clave, nombre, Icono, envs }) => {
          const activa = Boolean(canales[clave]);
          return (
            <div key={clave} className={`tarjeta-canal ${activa ? 'activa' : ''}`}>
              <div className="tarjeta-canal-cabecera">
                <span className="tarjeta-canal-nombre"><Icono size={17} /> {nombre}</span>
                {activa
                  ? <span className="chip chip-ok"><CheckCircle size={12} /> Activo</span>
                  : <span className="chip chip-muted"><XCircle size={12} /> Sin configurar</span>}
              </div>
              {activa ? (
                <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                  Recibirás por aquí las alertas de perfiles, seguimientos y municipios favoritos.
                </div>
              ) : (
                <>
                  <div style={{ fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
                    Variables de entorno a configurar en Coolify:
                  </div>
                  <ul className="lista-env">
                    {envs.map((e) => <li key={e}><code>{e}</code></li>)}
                  </ul>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
        <div className="card-titulo"><Clock size={16} color="var(--info)" /> Escaneo programado</div>
        <div className="tira-radar">
          <span>Cron diario a las <b style={{ color: 'var(--text-primary)' }}>04:00</b> (hora de Madrid)</span>
          {proximo && <span>· Próxima ejecución: {proximo}</span>}
          <span style={{ flex: 1 }} />
          {syncMsg && <span className="chip chip-info">{syncMsg}</span>}
          <button type="button" className="btn btn-primary" onClick={onSync} disabled={syncing}>
            <RefreshCw size={15} className={syncing ? 'spin' : ''} />
            {syncing ? 'Sincronizando...' : 'Sincronizar ahora'}
          </button>
        </div>
        {estadoRadar && (
          <div style={{ marginTop: '0.85rem', fontSize: '0.83rem', color: 'var(--text-secondary)' }}>
            {estadoRadar.total_convocatorias} convocatorias registradas · {estadoRadar.seguidas} en
            seguimiento · {estadoRadar.municipios_favoritos ?? 0} municipios favoritos
          </div>
        )}
      </div>

      <div className="glass-card">
        <div className="card-titulo">Fuentes monitorizadas ({FUENTES.length})</div>
        <ul className="lista-fuentes">
          {FUENTES.map((f) => (
            <li key={f.nombre}>
              <span>{f.nombre}</span>
              <span>{f.cubre}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default Estado;
