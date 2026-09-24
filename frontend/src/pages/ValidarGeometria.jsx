import React from 'react';
import { GeometriaViewer } from '../components/GeometriaViewer/GeometriaViewer';

export const ValidarGeometria = ({ idPlano, idModelo2D, onGeometriaConfirmed, onNext }) => {
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Validar Geometría 2D
      </h1>

      <div className="card-hover bg-white border border-gray-200 rounded-md">
        <GeometriaViewer
          idPlano={idPlano}
          idModelo2D={idModelo2D}
          onGeometriaConfirmed={onGeometriaConfirmed}
          onNext={onNext}
        />
      </div>
    </div>
  );
};

export default ValidarGeometria;
