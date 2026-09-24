import React from 'react';
import { Info } from 'lucide-react';
import { NivelProteccionForm } from '../components/NivelProteccionForm/NivelProteccionForm';

export const NivelProteccion = ({ idProyecto, onCalculated, onNext }) => {
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Nivel de Protección SPDA
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 4 de 7</strong> Evaluación de riesgo según Norma IEC 62305 / IRAM 2184 para definir el Nivel de Protección (I a IV) y radio de esfera rodante.
        </div>
      </div>

      <div className="card-hover bg-white border border-gray-200 rounded-md">
        <NivelProteccionForm
          idProyecto={idProyecto}
          onCalculated={onCalculated}
          onNext={onNext}
        />
      </div>
    </div>
  );
};

export default NivelProteccion;
