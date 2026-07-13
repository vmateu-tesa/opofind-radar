import React from 'react';

// Chip de estado del plazo de instancias. Convencion del backend
// (core/plazos.py): dias_restantes 0 = hoy es el ultimo dia; "quedan N
// dias" en sentido coloquial (contando hoy) es dias_restantes + 1.
function PlazoChip({ estado, dias, fechaInicio }) {
  if (!estado || estado === 'sin_fechas') {
    return <span className="chip chip-muted">Sin plazo</span>;
  }
  if (estado === 'proximamente') {
    return <span className="chip chip-info">Abre{fechaInicio ? ` el ${fechaInicio}` : ' pronto'}</span>;
  }
  if (estado === 'cerrado') {
    return <span className="chip chip-danger">Cerrado</span>;
  }
  if (estado === 'cierra_pronto') {
    return (
      <span className="chip chip-warn">
        {dias === 0 ? <b>¡ÚLTIMO DÍA hoy!</b> : <>Cierra pronto · <b>quedan {dias + 1} días</b></>}
      </span>
    );
  }
  // abierto
  return (
    <span className="chip chip-ok">
      {Number.isInteger(dias) ? `Abierto · quedan ${dias + 1} días` : 'Abierto'}
    </span>
  );
}

export default PlazoChip;
