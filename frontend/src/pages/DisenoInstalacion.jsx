import React from 'react';
import { Info } from 'lucide-react';
// import { PlanoUploader } from '../components/PlanoUploader/PlanoUploader';

export const DisenoInstalacion = ({ idProyecto, onPlanoUploaded, onNext }) => {
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Diseño de la Instalación
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 2 de 7 (HU02):</strong> Cargue el plano del edificio (.DXF o .PDF). El sistema extraerá automáticamente el modelo 2D y cotas de altura.
        </div>
      </div>

      <div className="card-hover bg-white border border-gray-200 rounded-md">
        <PlanoUploader
          idProyecto={idProyecto}
          onPlanoUploaded={onPlanoUploaded}
          onNext={onNext}
        />
      </div>
    </div>
  );
};

export default DisenoInstalacion;
