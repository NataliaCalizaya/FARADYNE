import React from 'react';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';

export const STEPS = [
  { id: 0, label: 'Datos del Proyecto' },
  { id: 1, label: 'Cargar y Validar Plano' },
  { id: 2, label: 'Generar Modelo 3D' },
  { id: 3, label: 'Nivel de Protección' },
  { id: 4, label: 'Ubicación de Mástiles' },
  { id: 5, label: 'Listado de Materiales' },
  { id: 6, label: 'Memoria Descriptiva' },
];

export const StepperBar = ({ currentStep, onStepChange, isGeometriaValidada = false }) => {
  const handlePrev = () => {
    if (currentStep > 0) onStepChange(currentStep - 1);
  };

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      if (currentStep === 1 && !isGeometriaValidada) return;
      onStepChange(currentStep + 1);
    }
  };

  return (
    <div className="h-[52px] bg-white border-b border-gray-200 flex items-center justify-between px-5 select-none sticky top-0 z-30 shadow-sm">
      <button
        type="button"
        onClick={handlePrev}
        disabled={currentStep === 0}
        className="w-8 h-8 rounded border border-gray-300 bg-white flex items-center justify-center text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
        title="Paso anterior"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="flex items-center gap-0 overflow-x-auto py-1 px-2 no-scrollbar">
        {STEPS.map((step, idx) => {
          const isDone = currentStep > step.id;
          const isActive = currentStep === step.id;
          // Step 2 (Generar Modelo 3D) is disabled if step 1 hasn't validated geometry
          const isDisabled = step.id === 2 && !isGeometriaValidada && currentStep < 2;

          return (
            <React.Fragment key={step.id}>
              <div
                onClick={() => {
                  if (!isDisabled) onStepChange(step.id);
                }}
                className={`flex flex-col items-center gap-1 px-2 group ${
                  isDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
                }`}
                title={isDisabled ? 'Debe confirmar la geometría en el paso anterior' : ''}
              >
                <div
                  className={`w-3.5 h-3.5 rounded-full flex items-center justify-center transition-all relative ${
                    isDone
                      ? 'bg-brand-blue border-2 border-brand-blue text-white'
                      : isActive
                      ? 'border-2 border-brand-blue bg-white shadow-[0_0_0_3px_rgba(26,109,186,0.15)]'
                      : 'border-2 border-gray-300 bg-white group-hover:border-gray-400'
                  }`}
                >
                  {isDone && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                  {isActive && (
                    <div className="w-1.5 h-1.5 rounded-full bg-brand-blue" />
                  )}
                </div>
                <span
                  className={`text-[10px] font-medium whitespace-nowrap transition-colors ${
                    isActive
                      ? 'text-brand-blue font-bold'
                      : isDone
                      ? 'text-gray-700'
                      : 'text-gray-400 group-hover:text-gray-600'
                  }`}
                >
                  {step.label}
                </span>
              </div>

              {idx < STEPS.length - 1 && (
                <div
                  className={`h-[1px] w-6 md:w-10 mb-4 transition-colors ${
                    currentStep > step.id ? 'bg-brand-blue' : 'bg-gray-200'
                  }`}
                />
              )}
            </React.Fragment>
          );
        })}
      </div>

      <button
        type="button"
        onClick={handleNext}
        disabled={currentStep === STEPS.length - 1 || (currentStep === 1 && !isGeometriaValidada)}
        className="w-8 h-8 rounded border border-gray-300 bg-white flex items-center justify-center text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
        title="Paso siguiente"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  );
};

export default StepperBar;
