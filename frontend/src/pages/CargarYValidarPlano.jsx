import react, { useState } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle2, Loader2, Cpu, Edit3, Info } from 'lucide-react';
import { planosApi } from '../api/planos';
import { GeometriaViewer } from '../components/GeometriaViewer/GeometriaViewer';

export const CargarYValidarPlano = ({ idProyecto, onPlanoUploaded, onGeometriaConfirmed, onNext }) => {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [uploadedData, setUploadedData] = useState(null);
  const [isValidated, setIsValidated] = useState(false);

  const handleFileChange = (e) => {
    const selected = e.target.files[0];
    if (selected) {
      setFile(selected);
      setError(null);
    }
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
      const msg = err.response?.data?.detail || 'Error al procesar el archivo en el servidor.';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmed = (geoData) => {
    setIsValidated(true);
    if (onGeometriaConfirmed) {
      onGeometriaConfirmed(geoData);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Cargar y Validar Plano
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div><strong>Paso 2 de 7:</strong> Cargue el plano y valide la geometría extraída antes de continuar.</div>
      </div>

      {error && (
        <div className="animate-fade-in p-3 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-start gap-2 text-xs">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold">Error al cargar plano:</strong> {error}
          </div>
        </div>
      )}

      {/* File Upload Header */}
      <div className="card-hover bg-white border border-gray-200 rounded-md p-4 shadow-sm">
        <label className="flex items-center gap-3 cursor-pointer group">
          <div className="w-10 h-10 rounded bg-blue-50 text-brand-blue flex items-center justify-center group-hover:bg-blue-100 group-hover:shadow-glow-sm transition">
            <Upload className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <div className="font-semibold text-sm text-gray-800">
              {file ? file.name : 'Cargar Plano (.DXF, .PDF)'}
            </div>
            <div className="text-xs text-gray-500">
              {file
                ? `${(file.size / 1024).toFixed(1)} KB`
                : 'Seleccione o arrastre el archivo plano de la instalación para la extracción automática'}
            </div>
          </div>
          <input
            type="file"
            accept=".dxf,.pdf"
            onChange={handleFileChange}
            className="hidden"
          />
          <button
            type="button"
            onClick={handleUpload}
            disabled={!file || loading}
            className="btn-electric px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded text-xs disabled:opacity-50 flex items-center gap-1.5 transition"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Interpretando Trazos...
              </>
            ) : (
              'Subir e Interpretar Plano'
            )}
          </button>
        </label>
      </div>

      {/* 2D Geometry Corrector Section */}
      {uploadedData ? (
        <div className="step-transition space-y-4">
          <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 text-emerald-800 p-3 rounded-md text-xs">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                Plano <strong>{uploadedData.nombre_archivo}</strong> interpretado correctamente. Revise y edite la geometría 2D a continuación.
              </span>
            </div>
          </div>

          <GeometriaViewer
            idPlano={uploadedData.id}
            idModelo2D={uploadedData.id_modelo2d}
            onGeometriaConfirmed={handleConfirmed}
            onNext={onNext}
          />
        </div>
      ) : (
        <div className="card-hover bg-slate-50 border border-dashed border-gray-300 rounded-md h-[300px] flex flex-col items-center justify-center p-6 text-center">
          <Edit3 className="w-10 h-10 text-gray-400 mb-3" />
          <h3 className="font-semibold text-sm text-gray-700">Sin plano cargado</h3>
          <p className="text-xs text-gray-500 max-w-md mt-1">
            Cargue un archivo .DXF o .PDF en el control superior. Al finalizar la interpretación, el corrector 2D interactivo cargará automáticamente los perímetros y cotas detectados.
          </p>
        </div>
      )}
    </div>
  );
};

export default CargarYValidarPlano;
