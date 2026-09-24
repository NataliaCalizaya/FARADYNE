import React from 'react';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';

export const STEPS = [
  { id: 0, label: 'Datos del Proyecto', desc: 'Nombre, cliente, región y proyectista.' },
  { id: 1, label: 'Cargar y Validar Plano', desc: 'Subí el plano y confirmá la geometría.' },
  { id: 2, label: 'Generar Modelo 3D', desc: 'Generación automática del modelo 3D.' },
  { id: 3, label: 'Nivel de Protección', desc: 'Cálculo del nivel de riesgo (NP).' },
  { id: 4, label: 'Ubicación de Mástiles', desc: 'Posicionamiento de mástiles captores.' },
  { id: 5, label: 'Listado de Materiales', desc: 'Materiales necesarios para la instalación.' },
  { id: 6, label: 'Memoria Descriptiva', desc: 'Documento final del proyecto.' },
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

  const progressPercent = (currentStep / (STEPS.length - 1)) * 100;

  return (
    <div className="bg-white/80 backdrop-blur-md border-b border-gray-200/80 sticky top-0 z-30 shadow-sm">      <div className="h-[68px] flex items-center justify-between px-5 select-none">
      <button
        type="button"
        onClick={handlePrev}
        disabled={currentStep === 0}
        className="w-9 h-9 shrink-0 rounded border border-gray-300 bg-white flex items-center justify-center text-gray-600 hover:bg-gray-50 hover:border-brand-blue/40 disabled:opacity-40 disabled:cursor-not-allowed transition"
        title="Paso anterior"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      <div className="relative flex-1 flex items-center justify-between overflow-x-auto no-scrollbar px-4 md:px-8">
        {/* Track de fondo */}
        <div className="absolute left-4 right-4 md:left-8 md:right-8 top-5 h-[3px] bg-gray-200 rounded-full" />
        {/* Fill animado */}
        <div
          className="stepper-progress-fill absolute left-4 md:left-8 top-5 h-[3px] bg-brand-blue rounded-full"
          style={{
            width: `calc((100% - ${window.innerWidth < 768 ? '2rem' : '4rem'}) * ${progressPercent / 100})`,
          }}
        />

        {STEPS.map((step) => {
          const isDone = currentStep > step.id;
          const isActive = currentStep === step.id;
          const isDisabled = step.id === 2 && !isGeometriaValidada && currentStep < 2;

          return (
            <div
              key={step.id}
              onClick={() => {
                if (!isDisabled) onStepChange(step.id);
              }}
              className={`group relative z-10 flex flex-col items-center gap-1.5 shrink-0 px-1.5 ${isDisabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
                }`}
            >
              {/* Tooltip */}
              <div className="stepper-tooltip absolute -top-9 left-1/2 whitespace-nowrap bg-slate-900 text-white text-[10px] px-2.5 py-1.5 rounded shadow-lg z-20">
                {isDisabled ? 'Confirmá la geometría en el paso anterior' : step.desc}
              </div>

              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-[11px] font-bold transition-all duration-300 ${isDone
                  ? 'bg-brand-blue border-2 border-brand-blue text-white'
                  : isActive
                    ? 'border-2 border-brand-blue bg-white text-brand-blue shadow-glow-md stepper-active-glow'
                    : 'border-2 border-gray-300 bg-white text-gray-400 group-hover:border-gray-400 group-hover:text-gray-600'
                  }`}
              >
                {isDone ? <Check className="w-4 h-4 stroke-[3]" /> : step.id + 1}
              </div>

              <span
                className={`hidden md:block text-[10px] font-medium whitespace-nowrap transition-colors max-w-[90px] text-center leading-tight ${isActive
                  ? 'text-brand-blue font-bold'
                  : isDone
                    ? 'text-gray-700'
                    : 'text-gray-400 group-hover:text-gray-600'
                  }`}
              >
                {step.label}
              </span>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        onClick={handleNext}
        disabled={currentStep === STEPS.length - 1 || (currentStep === 1 && !isGeometriaValidada)}
        className="w-9 h-9 shrink-0 rounded border border-gray-300 bg-white flex items-center justify-center text-gray-600 hover:bg-gray-50 hover:border-brand-blue/40 disabled:opacity-40 disabled:cursor-not-allowed transition"
        title="Paso siguiente"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
    </div>
  );
};

export default StepperBar;