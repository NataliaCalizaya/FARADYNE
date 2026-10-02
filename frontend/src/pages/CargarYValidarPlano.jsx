import React, { useRef, useState } from 'react';
import {
  Upload,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Edit3,
  X,
  FileUp,
  ArrowUpFromLine,
  Sparkles,
  RefreshCw,
  Info,
} from 'lucide-react';
import { planosApi } from '../api/planos';
import { GeometriaViewer } from '../components/GeometriaViewer/GeometriaViewer';

const ACCEPTED = /\.(dxf|pdf)$/i;

const formatSize = (bytes) =>
  bytes > 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(1)} MB`
    : `${(bytes / 1024).toFixed(1)} KB`;

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
      <div>
        <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
          Cargar y Validar Plano
        </h1>
        <div className="workflow-notice project-data-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
          <Info className="w-4 h-4 shrink-0" />
          <div>
            <strong>Paso 2 de 7: </strong>
            Suba su plano y el sistema extraerá automáticamente la geometría.
          </div>
        </div>
      </div>

      {/* ---------- Error ---------- */}
      {error && (
        <div
          role="alert"
          className="animate-fade-in p-3.5 bg-red-50 border border-red-200 text-red-700 rounded-xl flex items-start gap-2.5 text-xs shadow-sm"
        >
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <strong className="font-semibold">Error al cargar plano:</strong>{' '}
            {error}
          </div>
          <button
            type="button"
            onClick={() => setError(null)}
            className="p-1 rounded-md text-red-400 hover:text-red-600 hover:bg-red-100 transition"
            aria-label="Cerrar mensaje"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ---------- Zona de carga ---------- */}
      {!hasPlano && !file && !loading ? (
        /* Gran zona de drop visual cuando no hay nada */
        <label
          className={`upload-drop-zone group relative cursor-pointer block rounded-2xl border-2 border-dashed transition-all duration-300 ${dragging
            ? 'border-brand-blue bg-blue-50/80 ring-4 ring-blue-100 scale-[1.01]'
            : 'border-gray-300 hover:border-brand-blue/60 hover:bg-blue-50/30 bg-white'
            }`}
          onDragOver={(e) => {
            e.preventDefault();
            if (!loading) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={loading ? undefined : handleDrop}
        >
          <div className="flex flex-col items-center justify-center py-14 px-8 text-center">
            {/* Icono animado */}
            <div
              className={`w-20 h-20 rounded-2xl flex items-center justify-center mb-5 transition-all duration-300 ${dragging
                ? 'bg-brand-blue text-white shadow-lg shadow-blue-300/40 scale-110'
                : 'bg-gradient-to-br from-blue-50 to-blue-100/80 text-brand-blue group-hover:shadow-md group-hover:shadow-blue-200/40 group-hover:scale-105'
                }`}
            >
              {dragging ? (
                <FileUp className="w-9 h-9 animate-bounce" />
              ) : (
                <ArrowUpFromLine className="w-9 h-9" />
              )}
            </div>

            <h3 className="font-condensed font-bold text-lg text-gray-800 mb-1.5">
              {dragging ? 'Suelte el archivo aquí' : 'Arrastre su plano aquí'}
            </h3>
            <p className="text-sm text-gray-500 mb-5 max-w-sm">
              {dragging
                ? 'Detectamos su archivo, suéltelo para continuar'
                : 'o haga clic en esta zona para seleccionarlo desde su equipo'}
            </p>

            {/* Chips de formatos */}
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 text-blue-700 text-[11px] font-semibold rounded-full border border-blue-200/60">
                <FileText className="w-3 h-3" />
                .DXF
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-50 text-red-600 text-[11px] font-semibold rounded-full border border-red-200/60">
                <FileText className="w-3 h-3" />
                .PDF
              </span>
            </div>

            <p className="text-[11px] text-gray-400 mt-4">
              Se extraen perímetros y cotas automáticamente
            </p>
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
      ) : !hasPlano ? (
        /* Archivo seleccionado / cargando – vista compacta */
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
          <div className="flex flex-wrap items-center gap-4 p-4">
            {/* Icono de archivo */}
            <div
              className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 transition ${isPdf
                ? 'bg-red-50 text-red-500'
                : 'bg-blue-50 text-brand-blue'
                }`}
            >
              <FileText className="w-6 h-6" />
            </div>

            {/* Info del archivo */}
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-sm text-gray-800 truncate">
                {file?.name}
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                {file
                  ? `${isPdf ? 'PDF' : 'DXF'} · ${formatSize(file.size)}`
                  : ''}
              </div>
            </div>

            <input
              ref={!inputRef.current ? inputRef : undefined}
              type="file"
              accept=".dxf,.pdf"
              disabled={loading}
              onChange={(e) => selectFile(e.target.files[0])}
              className="hidden"
            />

            {/* Acciones */}
            <div className="flex items-center gap-2">
              {file && !loading && (
                <button
                  type="button"
                  onClick={clearFile}
                  className="p-2.5 rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition border border-transparent hover:border-red-200"
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
                className="btn-electric px-5 py-2.5 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded-lg text-sm disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2 transition shadow-md shadow-blue-200/30"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Interpretando trazos…</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Subir e interpretar</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Barra de progreso */}
          {loading && (
            <div className="h-1.5 bg-blue-100 overflow-hidden rounded-b-xl">
              <div
                className="h-full bg-gradient-to-r from-brand-blue via-sky-400 to-brand-blue rounded"
                style={{
                  width: '40%',
                  animation: 'uploadBarSlide 1.6s ease-in-out infinite',
                }}
              />
            </div>
          )}
        </div>
      ) : (
        /* Ya tiene plano – opción compacta de reemplazo */
        <div
          className="card-hover bg-white border border-gray-200 rounded-xl shadow-sm transition-all"
          onDragOver={(e) => {
            e.preventDefault();
            if (!loading) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={loading ? undefined : handleDrop}
        >
          <div className="flex flex-wrap items-center gap-4 p-3.5">
            <label className="flex items-center gap-3 flex-1 min-w-[200px] group cursor-pointer">
              <div className="w-9 h-9 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0 group-hover:bg-blue-50 group-hover:text-brand-blue transition">
                <CheckCircle2 className="w-5 h-5 group-hover:hidden" />
                <Upload className="w-5 h-5 hidden group-hover:block" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-sm text-gray-800 truncate group-hover:text-brand-blue transition">
                  Plano cargado correctamente
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  Haga clic aquí si desea reemplazarlo por otro archivo
                </div>
              </div>
              <input
                ref={inputRef}
                type="file"
                accept=".dxf,.pdf"
                disabled={loading}
                onChange={(e) => {
                  selectFile(e.target.files[0]);
                }}
                className="hidden"
              />
            </label>

            {file && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-600 font-medium truncate max-w-[150px]">
                  {file.name}
                </span>
                <button
                  type="button"
                  onClick={clearFile}
                  className="p-1.5 rounded-md text-gray-400 hover:text-red-500 hover:bg-red-50 transition"
                  aria-label="Quitar archivo"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={loading}
                  className="btn-electric px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded-lg text-xs disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 transition shadow-md shadow-blue-200/30"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Procesando…
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-3.5 h-3.5" />
                      Reemplazar
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {loading && (
            <div className="h-1 bg-blue-100 overflow-hidden rounded-b-xl">
              <div
                className="h-full bg-gradient-to-r from-brand-blue via-sky-400 to-brand-blue rounded"
                style={{
                  width: '40%',
                  animation: 'uploadBarSlide 1.6s ease-in-out infinite',
                }}
              />
            </div>
          )}
        </div>
      )}

      {/* ---------- Corrector 2D / Estado vacío ---------- */}
      {hasPlano ? (
        <div className="step-transition space-y-4">
          {uploadedData.nombre_archivo && (
            <div className="flex items-center gap-2.5 bg-emerald-50 border border-emerald-200 text-emerald-800 p-3.5 rounded-xl text-xs shadow-sm">
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
        <div className="bg-gradient-to-br from-slate-50 to-white border-2 border-dashed border-gray-200 rounded-2xl min-h-[240px] flex flex-col items-center justify-center p-10 text-center">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-gray-100 to-white shadow-sm flex items-center justify-center mb-4">
            <Edit3 className="w-7 h-7 text-gray-350" style={{ color: '#a3aebf' }} />
          </div>
          <h3 className="font-condensed font-semibold text-base text-gray-600">
            El corrector de geometría aparecerá aquí
          </h3>
          <p className="text-xs text-gray-400 max-w-sm mt-2 leading-relaxed">
            Cuando suba un archivo .DXF o .PDF, se mostrarán los perímetros y
            cotas detectados listos para revisar y editar.
          </p>
        </div>
      )}
    </div>
  );
};

export default CargarYValidarPlano;