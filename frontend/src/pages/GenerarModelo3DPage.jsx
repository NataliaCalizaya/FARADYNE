import React, { useState, useEffect } from 'react';
import { Box, AlertCircle, CheckCircle2, ArrowRight, ArrowLeft, Loader2, Info } from 'lucide-react';
import { Modelo3DViewer } from '../components/Modelo3DViewer/Modelo3DViewer';
import { modelos3dApi } from '../api/modelos3d';

export const GenerarModelo3DPage = ({ idModelo2D, idModelo3D, onNext, onBack, onModelo3DGenerated }) => {
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
      // El schema Pydantic acepta tanto 'idModelo2D' (alias) como 'id_modelo2d'
      const payload = { id_modelo2d: String(id2d) };

      const data = await modelos3dApi.generateModelo3D(payload);
      setModelo3dData(data);
      // Propagar el ID del modelo 3D al componente padre
      if (onModelo3DGenerated) onModelo3DGenerated(data);
    } catch (err) {
      console.log('Respuesta de FastAPI (detalle del error):', err.response?.data);
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
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Generar Modelo 3D
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div><strong>Paso 3 de 7:</strong> Genere y revise el modelo tridimensional a partir de la geometría validada.</div>
      </div>

      {error && (
        <div className="animate-fade-in p-3 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-start gap-2 text-xs">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold">Error en extrusión 3D:</strong> {error}
          </div>
        </div>
      )}

      {loading ? (
        <div className="header-grid-bg bg-slate-900 border border-slate-800 rounded-md h-[400px] flex flex-col items-center justify-center text-white">
          <Loader2 className="w-8 h-8 text-brand-blue animate-spin mb-3" />
          <p className="text-sm font-semibold">Generando extrusión volumétrica 3D a partir del plano 2D...</p>
          <p className="text-xs text-slate-400 mt-1">Calculando elevaciones y pendientes por capa</p>
        </div>
      ) : (
        <div className="step-transition space-y-4">
          <div className="card-hover h-[460px] rounded-md overflow-hidden">
            <Modelo3DViewer idModelo3D={modelo3dData?.id || idModelo3D} idModelo2D={idModelo2D} />
          </div>

          <div className="flex justify-between pt-2">
            <button
              type="button"
              onClick={onBack}
              className="px-5 py-2 border border-slate-300 hover:border-brand-blue text-slate-600 hover:text-brand-blue font-bold rounded text-xs flex items-center gap-1.5 transition shadow-sm bg-white"
            >
              <ArrowLeft className="w-4 h-4" /> Volver a Cargar y Validar Plano
            </button>
            <button
              type="button"
              onClick={onNext}
              className="btn-electric px-5 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs flex items-center gap-1.5 transition shadow-sm"
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
