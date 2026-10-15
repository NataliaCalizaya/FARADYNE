import React, { useEffect, useState } from 'react';
import { Info, Download, Loader2 } from 'lucide-react';
import { getListadoMateriales } from '../api/materiales';

const toCsv = (items) => {
  const esc = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`;
  const rows = items.map((m) =>
    [m.codigo || '', m.descripcion, m.cantidad, m.unidad].map(esc).join(';')
  );
  return ['Código;Descripción;Cantidad;Unidad', ...rows].join('\r\n');
};

export const ListadoMateriales = ({ idProyecto, onNext }) => {
  const [items, setItems] = useState([]);
  const [totalMastiles, setTotalMastiles] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!idProyecto) {
      setLoading(false);
      setError('No hay un proyecto seleccionado.');
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getListadoMateriales(idProyecto)
      .then((data) => {
        if (cancelled) return;
        setItems(data.items || []);
        setTotalMastiles(data.total_mastiles || 0);
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [idProyecto]);

  const handleDownload = () => {
    // BOM para que Excel respete los acentos
    const blob = new Blob(['﻿' + toCsv(items)], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `listado_materiales_proyecto_${idProyecto}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="w-full space-y-5 px-3">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Listado de Materiales
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 6 de 7:</strong> Listado de materiales computados automáticamente según los
          mástiles captores guardados{!loading && !error ? ` (${totalMastiles} en total)` : ''}.
        </div>
      </div>

      <div className="card-hover bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-3">
        <span className="text-xs font-bold text-gray-700 uppercase">
          Cómputo Métrico de Materiales
        </span>

        {loading && (
          <div className="flex items-center gap-2 text-xs text-gray-500 py-4">
            <Loader2 className="w-4 h-4 animate-spin" /> Calculando materiales...
          </div>
        )}

        {!loading && error && (
          <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded text-xs">
            {error}
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="p-3 bg-slate-50 border border-gray-200 text-gray-600 rounded text-xs">
            Este proyecto todavía no tiene mástiles captores. Agregalos en el paso anterior para
            computar los materiales.
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border-collapse">
              <thead>
                <tr className="bg-slate-100 border-b border-gray-200 text-gray-700">
                  <th className="p-2 font-bold">Código</th>
                  <th className="p-2 font-bold">Descripción</th>
                  <th className="p-2 font-bold text-center">Cantidad</th>
                </tr>
              </thead>
              <tbody>
                {items.map((m, idx) => (
                  <tr
                    key={idx}
                    className="border-b border-gray-100 hover:bg-slate-50 transition-colors"
                  >
                    <td className="p-2 font-mono text-gray-600">{m.codigo || '—'}</td>
                    <td className="p-2 text-gray-800">{m.descripcion}</td>
                    <td className="p-2 text-center font-semibold text-brand-blue">
                      {m.cantidad}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex justify-between items-center pt-2">
          <button
            type="button"
            disabled={loading || items.length === 0}
            className="btn-electric px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold rounded text-xs flex items-center gap-1.5 transition disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={handleDownload}
          >
            <Download className="w-4 h-4 text-brand-blue" /> Descargar Listado (CSV)
          </button>

          <button
            type="button"
            onClick={onNext}
            className="btn-electric px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition"
          >
            Siguiente: Memoria Descriptiva →
          </button>
        </div>
      </div>
    </div>
  );
};

export default ListadoMateriales;