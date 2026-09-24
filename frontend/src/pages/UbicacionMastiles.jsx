import React from 'react';
import { Info } from 'lucide-react';
import { MastilPositioner } from '../components/MastilPositioner/MastilPositioner';

export const UbicacionMastiles = ({ idProyecto, idModelo3D, idModelo2D, onNext }) => {
  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900" >
        Ubicación de Mástiles Captores
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 5 de 7 (HU05 + HU03):</strong> Posicionamiento interactivo de mástiles pararrayos con cálculo tridimensional de cobertura por esfera rodante y visor volumétrico en 3D.
        </div>
      </div>

      <div className="card-hover bg-white border border-gray-200 rounded-md">
        <MastilPositioner
          idProyecto={idProyecto}
          idModelo3D={idModelo3D}
          idModelo2D={idModelo2D}
          onNext={onNext}
        />
      </div>
    </div>
  );
};

export default UbicacionMastiles;
