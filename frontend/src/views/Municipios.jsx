import React, { useMemo, useState } from 'react';
import { Search, Heart, X, AlertTriangle } from 'lucide-react';
import { normaliza } from '../api';

// Gestión de municipios favoritos: cualquier oferta NUEVA o ACTUALIZADA de
// un municipio favorito dispara aviso por Telegram/WhatsApp/Email, coincida
// o no con los perfiles de alerta.
function Municipios({ municipios, onToggleFavorito, sinCanales }) {
  const [busqueda, setBusqueda] = useState('');

  const favoritos = useMemo(() => municipios.filter((m) => m.favorito), [municipios]);

  const visibles = useMemo(() => {
    const q = normaliza(busqueda);
    const lista = q
      ? municipios.filter((m) => normaliza(m.nombre).includes(q))
      : [...municipios];
    // Con actividad primero (más útiles), después alfabético.
    lista.sort((a, b) => {
      if ((b.total > 0) !== (a.total > 0)) return b.total > 0 ? 1 : -1;
      return normaliza(a.nombre).localeCompare(normaliza(b.nombre));
    });
    return lista;
  }, [municipios, busqueda]);

  return (
    <div>
      <h1 className="titulo-vista">Municipios</h1>
      <p className="subtitulo-vista">
        Marca municipios como favoritos y recibirás aviso de <b>cualquier</b> oferta nueva o
        actualizada en ellos por los canales activos, aunque no coincida con tus perfiles de alerta.
      </p>

      {sinCanales && (
        <div className="aviso-suave">
          <AlertTriangle size={14} style={{ verticalAlign: -2, marginRight: 6 }} />
          Ahora mismo no hay ningún canal de aviso configurado: los favoritos se guardan, pero las
          alertas no llegarán a ningún sitio hasta que actives Telegram, WhatsApp o email (pestaña Estado).
        </div>
      )}

      {favoritos.length > 0 && (
        <div className="glass-card" style={{ marginBottom: '1.25rem' }}>
          <div className="card-titulo"><Heart size={16} color="#fb7185" /> Tus favoritos</div>
          <div className="chips-favoritos">
            {favoritos.map((m) => (
              <span key={m.nombre} className="chip-favorito">
                {m.nombre}
                <small>{m.total} ofertas · {m.abiertas} abiertas</small>
                <button type="button" className="btn-icono" title="Quitar de favoritos"
                  onClick={() => onToggleFavorito(m.nombre, true)}>
                  <X size={15} />
                </button>
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="buscador" style={{ marginBottom: '1rem' }}>
        <Search size={17} />
        <input
          type="text"
          placeholder="Buscar municipio de la provincia..."
          value={busqueda}
          onChange={(e) => setBusqueda(e.target.value)}
        />
      </div>

      <div className="grid-municipios">
        {visibles.map((m) => (
          <div key={m.nombre} className={`tarjeta-municipio ${m.favorito ? 'favorita' : ''}`}>
            <div>
              <div className="tarjeta-municipio-nombre">{m.nombre}</div>
              <div className="tarjeta-municipio-datos">
                {m.total > 0 ? `${m.total} ofertas · ${m.abiertas} abiertas` : 'Sin ofertas registradas'}
              </div>
            </div>
            <button
              type="button"
              className={`btn-icono ${m.favorito ? 'activo-fav' : ''}`}
              title={m.favorito ? 'Quitar de favoritos' : 'Añadir a favoritos (avisa de toda oferta nueva aquí)'}
              onClick={() => onToggleFavorito(m.nombre, m.favorito)}
            >
              <Heart size={18} fill={m.favorito ? 'currentColor' : 'none'} />
            </button>
          </div>
        ))}
        {visibles.length === 0 && (
          <div className="estado-vacio" style={{ gridColumn: '1 / -1' }}>
            Ningún municipio coincide con "{busqueda}".
          </div>
        )}
      </div>
    </div>
  );
}

export default Municipios;
