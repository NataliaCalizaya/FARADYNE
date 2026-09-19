import React from 'react';
import { Info, Download, Edit2 } from 'lucide-react';

// TODO: conectar cuando exista el endpoint de Listado de Materiales
export const ListadoMateriales = ({ onNext }) => {
  const materials = [
    { code: '77902610', desc: 'Adaptación cable mástil 3/6m', qty: '5' },
    { code: '77908750', desc: 'Mástil galvanizado 4m', qty: '3' },
    { code: '77460000', desc: 'Cable de cobre 50mm²', qty: '475 m' },
    { code: '77660141', desc: 'Soporte piramidal universal hormigón', qty: '281' },
    { code: '77123900', desc: 'Conector de cruz para conductor plano', qty: '42' },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold font-condensed text-gray-900">
        Listado de Materiales
      </h1>

      <div className="p-3 bg-blue-50 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 6 de 7:</strong> Listado de materiales computados automáticamente según el diseño de pararrayos optimizado.
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-gray-700 uppercase">
            Cómputo Métrico de Materiales
          </span>
          <button
            type="button"
            disabled
            className="px-2.5 py-1 bg-gray-100 text-gray-400 border border-gray-200 rounded text-xs cursor-not-allowed flex items-center gap-1"
            title="// TODO: conectar cuando exista el endpoint"
          >
            <Edit2 className="w-3 h-3" /> Editar Lista (Deshabilitado)
          </button>
        </div>

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
              {materials.map((m, idx) => (
                <tr key={idx} className="border-b border-gray-100 hover:bg-slate-50">
                  <td className="p-2 font-mono text-gray-600">{m.code}</td>
                  <td className="p-2 text-gray-800">{m.desc}</td>
                  <td className="p-2 text-center font-semibold text-brand-blue">{m.qty}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex justify-between items-center pt-2">
          <button
            type="button"
            className="px-4 py-2 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold rounded text-xs flex items-center gap-1.5 transition"
            onClick={() => alert('Descargando listado de materiales...')}
          >
            <Download className="w-4 h-4 text-brand-blue" /> Descargar Listado (CSV)
          </button>

          <button
            type="button"
            onClick={onNext}
            className="px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition"
          >
            Siguiente: Memoria Descriptiva →
          </button>
        </div>
      </div>
    </div>
  );
};

export default ListadoMateriales;
