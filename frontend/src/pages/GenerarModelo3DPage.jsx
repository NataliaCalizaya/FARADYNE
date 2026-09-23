import React, { useState, useEffect } from 'react';
import { Box, AlertCircle, CheckCircle2, ArrowRight, Loader2 } from 'lucide-react';
import { Modelo3DViewer } from '../components/Modelo3DViewer/Modelo3DViewer';
import { modelos3dApi } from '../api/modelos3d';

export const GenerarModelo3DPage = ({ idModelo2D, idModelo3D, onNext }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [modelo3dData, setModelo3dData] = useState(null);

  useEffect(() => {
    if (idModelo2D) {
      trigger3DExtrusion(idModelo2D);
    }
  }, [idModelo2D]);

  const trigger3DExtrusion = async (id2d) => {
    setLoading(true);
    setError(null);
    try {
      // Must send an object with id_modelo2d as an integer
      const payload = { idModelo2D: String(id2d) };
      //console.log("📦 Enviando payload a FastAPI:", payload);

      const data = await modelos3dApi.generateModelo3D(payload);
      setModelo3dData(data);
    } catch (err) {
      console.log("🚨 Respuesta de FastAPI (Motivo del 422):", err.response?.data);
      
      console.error('Error al generar modelo 3D:', err);
      const detail = err.response?.data?.detail;
      let msg = 'No se pudo generar el modelo 3D volumetricamente.';
      
      if (Array.isArray(detail)) {
        msg = detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join(' | ');
      } else if (typeof detail === 'string') {
        msg = detail;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full mx-auto space-y-4">
      <h1 className="text-2xl font-bold font-condensed text-gray-900">
        Generar Modelo 3D
      </h1>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-start gap-2 text-xs">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold">Error en extrusión 3D:</strong> {error}
          </div>
        </div>
      )}

      {loading ? (
        <div className="bg-slate-900 border border-slate-800 rounded-md h-[400px] flex flex-col items-center justify-center text-white">
          <Loader2 className="w-8 h-8 text-brand-blue animate-spin mb-3" />
          <p className="text-sm font-semibold">Generando extrusión volumétrica 3D a partir del plano 2D...</p>
          <p className="text-xs text-slate-400 mt-1">Calculando elevaciones y pendientes por capa</p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="h-[460px]">
            <Modelo3DViewer idModelo3D={modelo3dData?.id || idModelo3D} idModelo2D={idModelo2D} />
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={onNext}
              className="px-5 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs flex items-center gap-1.5 transition shadow-sm"
            >
              Continuar a Nivel de Protección <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GenerarModelo3DPage;
