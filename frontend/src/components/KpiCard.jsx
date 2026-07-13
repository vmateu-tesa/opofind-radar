import React from 'react';

// Tarjeta KPI clicable del Panel. `tono` es un color CSS (var(--ok),
// var(--warn)...) que tiñe la barra lateral y el icono.
function KpiCard({ icono: Icono, valor, etiqueta, tono, onClick }) {
  return (
    <button type="button" className="kpi" style={{ '--kpi-color': tono }} onClick={onClick}>
      <div className="kpi-cabecera">
        <Icono size={16} />
        <span className="kpi-etiqueta">{etiqueta}</span>
      </div>
      <div className="kpi-valor">{valor}</div>
    </button>
  );
}

export default KpiCard;
