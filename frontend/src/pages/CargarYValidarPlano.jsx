import React, { useRef, useState } from 'react';
import {
  Upload,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Edit3,
  Info,
  X,
  Check,
  FileUp,
} from 'lucide-react';
import { planosApi } from '../api/planos';
import { GeometriaViewer } from '../components/GeometriaViewer/GeometriaViewer';

const ACCEPTED = /\.(dxf|pdf)$/i;

const formatSize = (bytes) =>
  bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${(bytes / 1024).toFixed(1)} KB`;

/* Indicador de pasos: muestra en qué etapa del paso 2 está la persona. */
const Stepper = ({ current }) => {
  const steps = ['Cargar plano', 'Revisar y corregir la geometría'];

  return (
    <ol className="flex items-center gap-2 text-xs">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;

        return (
          <li key={label} className="flex items-center gap-2">
            <span
              className={`w-6 h-6 rounded-full flex items-center justify-center text-[11px] font-semibold transition-colors ${done
                  ? 'bg-emerald-500 text-white'
                  : active
                    ? 'bg-brand-blue text-white ring-4 ring-blue-100'
                    : 'bg-gray-200 text-gray-500'
                }`}
            >
              {done ? <Check className="w-3.5 h-3.5" /> : i + 1}
            </span>
            <span
              className={
                active
                  ? 'font-semibold text-gray-900'
                  : done
                    ? 'text-gray-700'
                    : 'text-gray-400'
              }
            >
              {label}
            </span>
            {i < steps.length - 1 && (
              <span
                className={`w-10 h-0.5 rounded transition-colors ${done ? 'bg-emerald-400' : 'bg-gray-200'
                  }`}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
};

export const CargarYValidarPlano = ({
  idProyecto,
  idPlano: idPlanoProp,
  idModelo2D: idModelo2DProp,
  onPlanoUploaded,
  onGeometriaConfirmed,
  onNext,
}) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  // Si App.jsx ya tiene un plano cargado de una visita anterior a este paso,
  // se reconstruye acá en vez de arrancar en null y perder el visor.
  const [uploadedData, setUploadedData] = useState(() =>
    idPlanoProp ? { id: idPlanoProp, id_modelo2d: idModelo2DProp } : null
  );

  const hasPlano = !!uploadedData?.id;

  const selectFile = (selected) => {
    if (!selected) return;

    if (!ACCEPTED.test(selected.name)) {
      setError('Formato no admitido. Use un archivo .DXF o .PDF.');
      return;
    }

    setFile(selected);
    setError(null);
  };

  const clearFile = (e) => {
    e?.preventDefault();
    e?.stopPropagation();
    setFile(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    selectFile(e.dataTransfer.files?.[0]);
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Por favor seleccione un archivo DXF o PDF.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await planosApi.uploadPlano(file, idProyecto);
      setUploadedData(data);
      if (onPlanoUploaded) {
        onPlanoUploaded(data);
      }
    } catch (err) {
      console.error('Upload error:', err);
      const msg =
        err.response?.data?.detail ||
        'Error al procesar el archivo en el servidor.';
      setError(typeof msg === 'string' ? msg : 'Error al procesar el archivo.');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmed = (geoData) => {
    if (onGeometriaConfirmed) {
      onGeometriaConfirmed(geoData);
    }
  };

  const isPdf = file && /\.pdf$/i.test(file.name);

  return (
    <div className="w-full space-y-5 px-3">
      {/* ---------- Encabezado ---------- */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs text-gray-500 flex items-center gap-1.5 mb-0.5">
            <Info className="w-3.5 h-3.5" />
            Paso 2 de 7
          </p>
          <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
            Cargar y Validar Plano
          </h1>
        </div>

        <Stepper current={hasPlano ? 1 : 0} />
      </div>

      {/* ---------- Error ---------- */}
      {error && (
        <div
          role="alert"
          className="animate-fade-in p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg flex items-start gap-2 text-xs"
        >
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <strong className="font-semibold">Error al cargar plano:</strong>{' '}
            {error}
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-600 transition"
            aria-label="Cerrar mensaje"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ---------- Zona de carga ---------- */}
      <div
        className={`card-hover bg-white border rounded-xl shadow-sm transition-all ${dragging
            ? 'border-brand-blue ring-4 ring-blue-100 bg-blue-50/60'
            : 'border-gray-200'
          }`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!loading) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={loading ? undefined : handleDrop}
      >
        <div
          className={`flex flex-wrap items-center gap-4 ${hasPlano ? 'p-3' : 'p-5'
            }`}
        >
          <label
            className={`flex items-center gap-4 flex-1 min-w-[260px] group ${loading ? 'cursor-wait' : 'cursor-pointer'
              }`}
          >
            <div
              className={`rounded-xl flex items-center justify-center shrink-0 transition ${hasPlano ? 'w-10 h-10' : 'w-14 h-14'
                } ${file
                  ? isPdf
                    ? 'bg-red-50 text-red-500'
                    : 'bg-blue-50 text-brand-blue'
                  : 'bg-blue-50 text-brand-blue group-hover:bg-blue-100 group-hover:scale-105'
                }`}
            >
              {file ? (
                <FileText className="w-6 h-6" />
              ) : dragging ? (
                <FileUp className="w-6 h-6 animate-bounce" />
              ) : (
                <Upload className="w-6 h-6" />
              )}
            </div>

            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-gray-800 truncate">
                {file
                  ? file.name
                  : dragging
                    ? 'Suelte el archivo aquí'
                    : hasPlano
                      ? 'Cargar otro plano'
                      : 'Arrastre su plano o haga clic para elegirlo'}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                {file
                  ? `${isPdf ? 'PDF' : 'DXF'} · ${formatSize(file.size)}`
                  : 'Formatos admitidos: .DXF y .PDF. Se extraen perímetros y cotas automáticamente.'}
              </div>
            </div>

            <input
              ref={inputRef}
              type="file"
              accept=".dxf,.pdf"
              disabled={loading}
              onChange={(e) => selectFile(e.target.files[0])}
              className="hidden"
            />
          </label>

          {file && !loading && (
            <button
              type="button"
              onClick={clearFile}
              className="p-2 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition"
              title="Quitar archivo"
              aria-label="Quitar archivo"
            >
              <X className="w-4 h-4" />
            </button>
          )}

          <button
            type="button"
            onClick={handleUpload}
            disabled={!file || loading}
            className="btn-electric px-5 py-2.5 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded-lg text-xs disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 transition shadow-sm"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Interpretando trazos...
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                {hasPlano ? 'Reemplazar plano' : 'Subir e interpretar'}
              </>
            )}
          </button>
        </div>

        {/* Barra indeterminada mientras el servidor procesa */}
        {loading && (
          <div className="h-1 bg-blue-100 overflow-hidden rounded-b-xl">
            <div className="h-full w-1/3 bg-brand-blue rounded animate-pulse" />
          </div>
        )}
      </div>

      {/* ---------- Corrector 2D ---------- */}
      {hasPlano ? (
        <div className="step-transition space-y-4">
          {uploadedData.nombre_archivo && (
            <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-lg text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                Plano <strong>{uploadedData.nombre_archivo}</strong>{' '}
                interpretado correctamente. Revise y corrija la geometría 2D
                a continuación.
              </span>
            </div>
          )}

          <GeometriaViewer
            idPlano={uploadedData.id}
            idModelo2D={uploadedData.id_modelo2d}
            onGeometriaConfirmed={handleConfirmed}
            onNext={onNext}
          />
        </div>
      ) : (
        <div className="bg-slate-50 border-2 border-dashed border-gray-300 rounded-xl min-h-[280px] flex flex-col items-center justify-center p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-white shadow-sm flex items-center justify-center mb-4">
            <Edit3 className="w-7 h-7 text-gray-400" />
          </div>
          <h3 className="font-semibold text-sm text-gray-700">
            Todavía no hay un plano cargado
          </h3>
          <p className="text-xs text-gray-500 max-w-md mt-1.5 leading-relaxed">
            Cuando suba un archivo .DXF o .PDF, aquí aparecerá el corrector
            2D con los perímetros y cotas detectados, listo para editar.
          </p>
        </div>
      )}
    </div>
  );
};

export default CargarYValidarPlano;