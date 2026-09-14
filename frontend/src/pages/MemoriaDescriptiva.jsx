import React from 'react';
import { CheckCircle2, Download, CloudUpload, FileText } from 'lucide-react';

// TODO: conectar cuando exista el endpoint de Memoria Descriptiva e historial de versiones
export const MemoriaDescriptiva = ({ projectData }) => {
  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="text-2xl font-bold font-condensed text-gray-900">
        Memoria Descriptiva & Documento Final
      </h1>

      <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md flex items-center gap-2 text-xs">
        <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
        <div>
          <strong>Paso 7 de 7 (FINAL):</strong> Vista previa de la Memoria Descriptiva según Ley 19.587 / Decreto 351/79 e IRAM 2184.
        </div>
      </div>

      {/* Professional PDF Preview Box */}
      <div className="bg-white border border-gray-300 rounded-lg shadow-lg overflow-hidden">
        {/* Document Header */}
        <div className="bg-gradient-to-r from-slate-900 to-brand-blue p-5 text-white flex justify-between items-center">
          <div>
            <div className="text-[10px] uppercase tracking-widest text-blue-200 font-semibold">
              Memoria Descriptiva
            </div>
            <div className="text-lg font-bold font-condensed">
              Sistema de Protección contra Rayos (SPDA)
            </div>
            <div className="text-xs text-blue-100 mt-0.5">
              Decreto 351/79 · Ley 19.587 · IRAM 2184
            </div>
          </div>
          <div className="bg-white/10 backdrop-blur px-3 py-1.5 rounded text-right border border-white/20">
            <div className="text-[9px] text-blue-200 uppercase">N° Expediente</div>
            <div className="text-sm font-bold font-mono">FAR-2026-0042</div>
          </div>
        </div>

        {/* Document Content */}
        <div className="p-6 space-y-5 text-xs text-gray-800 leading-relaxed font-sans">
          {/* Section 1 */}
          <div className="border-b border-gray-100 pb-3">
            <h3 className="text-xs font-bold text-brand-blue uppercase tracking-wider mb-2">
              1. Datos del Proyecto
            </h3>
            <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 p-3 rounded">
              <div><strong>Proyecto:</strong> {projectData?.nombre || 'Centro Comercial ABC'}</div>
              <div><strong>Expediente:</strong> FAR-2026-0042</div>
              <div><strong>Cliente:</strong> {projectData?.cliente || 'Constructora XYZ S.A.'}</div>
              <div><strong>Ubicación:</strong> {projectData?.region || 'Buenos Aires'}</div>
              <div><strong>Proyectista:</strong> {projectData?.proyectista || 'Ing. Juan García López'}</div>
              <div><strong>Fecha:</strong> {new Date().toLocaleDateString()}</div>
            </div>
          </div>

          {/* Section 2 */}
          <div className="border-b border-gray-100 pb-3">
            <h3 className="text-xs font-bold text-brand-blue uppercase tracking-wider mb-2">
              2. Descripción Técnica del Sistema
            </h3>
            <p className="text-justify text-gray-700">
              El presente proyecto describe la instalación del sistema de protección contra descargas atmosféricas (pararrayos) para la estructura proyectada. El cálculo de riesgo determinó la exigencia de un sistema clase NP II con eficiencia del 95% o superior, utilizando el método de la esfera rodante de radio R=30m.
            </p>
          </div>

          {/* Section 3 */}
          <div className="border-b border-gray-100 pb-3">
            <h3 className="text-xs font-bold text-brand-blue uppercase tracking-wider mb-2">
              3. Parámetros de Diseño Alcanzados
            </h3>
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 bg-blue-50 border-l-4 border-brand-blue rounded">
                <div className="text-[10px] text-brand-blue font-bold uppercase">Nivel de Protección</div>
                <div className="text-lg font-bold font-condensed text-slate-900">NP II (R=30m)</div>
              </div>
              <div className="p-3 bg-blue-50 border-l-4 border-brand-blue rounded">
                <div className="text-[10px] text-brand-blue font-bold uppercase">Cobertura Lograda</div>
                <div className="text-lg font-bold font-condensed text-slate-900">98% Cubierto</div>
              </div>
              <div className="p-3 bg-emerald-50 border-l-4 border-emerald-500 rounded">
                <div className="text-[10px] text-emerald-700 font-bold uppercase">Cumplimiento Legal</div>
                <div className="text-lg font-bold font-condensed text-emerald-800">CONFORME</div>
              </div>
            </div>
          </div>

          {/* Legal Exemption Clause */}
          <div className="bg-emerald-50 border border-emerald-200 p-3 rounded text-emerald-900">
            <div className="font-bold uppercase text-[10px] text-emerald-800 mb-1">
              Declaración de Cumplimiento Legal (Decreto 351/79 Anexo VI)
            </div>
            <p className="text-justify text-[11px]">
              El profesional firmante certifica que las instalaciones proyectadas garantizan la protección integral de las personas y bienes conforme a las normativas de seguridad laboral vigentes.
            </p>
          </div>
        </div>
      </div>

      {/* Export & Versioning Controls */}
      <div className="flex gap-3">
        <button
          type="button"
          onClick={() => alert('Generando informe completo en PDF...')}
          className="flex-1 py-2.5 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs flex items-center justify-center gap-2 transition"
        >
          <Download className="w-4 h-4" /> Descargar Memoria Descriptiva (PDF)
        </button>

        <button
          type="button"
          disabled
          className="py-2.5 px-4 bg-gray-100 border border-gray-300 text-gray-400 font-bold rounded text-xs cursor-not-allowed flex items-center gap-2"
          title="// TODO: conectar cuando exista el endpoint"
        >
          <CloudUpload className="w-4 h-4" /> Guardar Versión en Backend (Deshabilitado)
        </button>
      </div>
    </div>
  );
};

export default MemoriaDescriptiva;
