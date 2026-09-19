import React from 'react';
import { GeometriaViewer } from '../components/GeometriaViewer/GeometriaViewer';

export const ValidarGeometria = ({ idPlano, idModelo2D, onGeometriaConfirmed, onNext }) => {
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold font-condensed text-gray-900">
        Validar Geometría 2D
      </h1>

      <GeometriaViewer
        idPlano={idPlano}
        idModelo2D={idModelo2D}
        onGeometriaConfirmed={onGeometriaConfirmed}
        onNext={onNext}
      />
    </div>
  );
};

export default ValidarGeometria;
