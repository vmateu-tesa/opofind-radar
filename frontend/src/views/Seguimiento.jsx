import React, { useMemo } from 'react';
import { Star, Search } from 'lucide-react';
import ConvocatoriaRow from '../components/ConvocatoriaRow';

// Convocatorias marcadas con la estrella: cualquier novedad de estas avisa
// SIEMPRE por los canales activos. Orden: cierre más próximo primero.
function Seguimiento({ convocatorias, onToggleSeguimiento, onIA, onNavegar }) {
  const seguidas = useMemo(() => {
    const lista = convocatorias.filter((c) => c.seguimiento);
    lista.sort((a, b) => (a.dias_restantes ?? Infinity) - (b.dias_restantes ?? Infinity));
    return lista;
  }, [convocatorias]);

  return (
    <div>
      <h1 className="titulo-vista">Seguimiento</h1>
      <p className="subtitulo-vista">
        Cualquier novedad de una convocatoria seguida (nueva publicación, listas de admitidos,
        nombramiento, cambio de plazo...) te llega por los canales de aviso activos, coincida o
        no con tus perfiles de alerta.
      </p>

      {seguidas.length === 0 ? (
        <div className="glass-card estado-vacio">
          <Star size={28} />
          <span>
            No sigues ninguna convocatoria. Marca la estrella en cualquier fila de{' '}
            <b>Explorar</b> para recibir sus novedades.
          </span>
          <button type="button" className="btn btn-primary" onClick={() => onNavegar('explorar')}>
            <Search size={15} /> Ir a Explorar
          </button>
        </div>
      ) : (
        <div className="lista-filas">
          {seguidas.map((c) => (
            <ConvocatoriaRow key={c.id} c={c} onToggleSeguimiento={onToggleSeguimiento} onIA={onIA} />
          ))}
        </div>
      )}
    </div>
  );
}

export default Seguimiento;
