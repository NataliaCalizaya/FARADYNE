import React, { useState } from 'react';
import { StepperBar } from './components/Stepper/StepperBar';
import { DatosProyecto } from './pages/DatosProyecto';
import { CargarYValidarPlano } from './pages/CargarYValidarPlano';
import { GenerarModelo3DPage } from './pages/GenerarModelo3DPage';
import { NivelProteccion } from './pages/NivelProteccion';
import { UbicacionMastiles } from './pages/UbicacionMastiles';
import { ListadoMateriales } from './pages/ListadoMateriales';
import { MemoriaDescriptiva } from './pages/MemoriaDescriptiva';
import { Zap, User, Lock, ArrowRight } from 'lucide-react';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(true);
  const [currentStep, setCurrentStep] = useState(0);

  // Global Project State
  const [idProyecto, setIdProyecto] = useState(1);
  const [idPlano, setIdPlano] = useState(null);
  const [idModelo2D, setIdModelo2D] = useState(null);
  const [idModelo3D, setIdModelo3D] = useState(null);
  const [isGeometriaValidada, setIsGeometriaValidada] = useState(false);

  const [projectData, setProjectData] = useState({
    nombre: 'Centro Comercial ABC',
    cliente: 'Constructora XYZ S.A.',
    region: 'Buenos Aires',
    proyectista: 'Ing. Juan García López',
  });

  const handleLogin = (e) => {
    e.preventDefault();
    setIsAuthenticated(true);
  };

  const handlePlanoUploaded = (planoData) => {
    if (planoData) {
      if (planoData.id) setIdPlano(planoData.id);
      if (planoData.id_modelo2d) setIdModelo2D(planoData.id_modelo2d);
    }
  };

  const handleGeometriaConfirmed = (geoData) => {
    setIsGeometriaValidada(true);
  };

  const handleNivelCalculated = (nivelData) => {
    // Risk level saved
  };

  if (!isAuthenticated) {
    return (
      <div className="fixed inset-0 bg-[#0f1e30] flex items-center justify-center p-4 z-50">
        <div className="w-full max-w-sm bg-white rounded-lg p-8 shadow-2xl border border-gray-200">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-brand-blue rounded flex items-center justify-center text-white">
              <Zap className="w-6 h-6 fill-white" />
            </div>
            <div>
              <div className="font-condensed font-extrabold text-xl text-brand-blue tracking-wide">
                FARADYNE
              </div>
              <div className="text-[10px] text-gray-500 uppercase tracking-wider">
                Diseño y Cálculo de Pararrayos
              </div>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
                Usuario / Email
              </label>
              <div className="relative">
                <input
                  type="text"
                  defaultValue="proyectista@faradyne.com"
                  className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
                />
                <User className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
                Contraseña
              </label>
              <div className="relative">
                <input
                  type="password"
                  defaultValue="••••••••"
                  className="w-full pl-9 pr-3 py-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
                />
                <Lock className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-2.5 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition flex items-center justify-center gap-1.5"
            >
              Ingresar al Sistema <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100 flex flex-col font-sans">
      {/* Top Navbar Header */}
      <header className="bg-slate-900 text-white h-12 px-5 flex items-center justify-between border-b border-slate-800 shadow-md">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-brand-blue fill-brand-blue" />
          <span className="font-condensed font-bold text-lg tracking-wider">FARADYNE</span>
          <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
            v1.0.0
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-300">
          <div className="hidden sm:block">
            Proyecto: <strong className="text-white">{projectData.nombre}</strong>
          </div>
          <button
            onClick={() => setIsAuthenticated(false)}
            className="text-slate-400 hover:text-white text-[11px] underline"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      {/* Stepper Progress Bar */}
      <StepperBar
        currentStep={currentStep}
        onStepChange={(step) => setCurrentStep(step)}
        isGeometriaValidada={isGeometriaValidada}
      />

      {/* Page Content Viewport */}
      <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto">
        {currentStep === 0 && (
          <DatosProyecto
            projectData={projectData}
            setProjectData={setProjectData}
            onNext={() => setCurrentStep(1)}
          />
        )}
        {currentStep === 1 && (
          <CargarYValidarPlano
            idProyecto={idProyecto}
            onPlanoUploaded={handlePlanoUploaded}
            onGeometriaConfirmed={handleGeometriaConfirmed}
            onNext={() => setCurrentStep(2)}
          />
        )}
        {currentStep === 2 && (
          <GenerarModelo3DPage
            idModelo2D={idModelo2D}
            idModelo3D={idModelo3D}
            onNext={() => setCurrentStep(3)}
          />
        )}
        {currentStep === 3 && (
          <NivelProteccion
            idProyecto={idProyecto}
            onCalculated={handleNivelCalculated}
            onNext={() => setCurrentStep(4)}
          />
        )}
        {currentStep === 4 && (
          <UbicacionMastiles
            idProyecto={idProyecto}
            idModelo3D={idModelo3D}
            idModelo2D={idModelo2D}
            onNext={() => setCurrentStep(5)}
          />
        )}
        {currentStep === 5 && (
          <ListadoMateriales onNext={() => setCurrentStep(6)} />
        )}
        {currentStep === 6 && (
          <MemoriaDescriptiva projectData={projectData} />
        )}
      </main>
    </div>
  );
}

export default App;
