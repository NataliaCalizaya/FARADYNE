import React, { useState } from 'react';
import { StepperBar } from './components/Stepper/StepperBar';
import { DatosProyecto } from './pages/DatosProyecto';
import { CargarYValidarPlano } from './pages/CargarYValidarPlano';
import { GenerarModelo3DPage } from './pages/GenerarModelo3DPage';
import { NivelProteccion } from './pages/NivelProteccion';
import { UbicacionMastiles } from './pages/UbicacionMastiles';
import { ListadoMateriales } from './pages/ListadoMateriales';
import { MemoriaDescriptiva } from './pages/MemoriaDescriptiva';
import { LoginForm } from './components/auth/LoginForm';
import { Zap, Moon, Sun } from 'lucide-react';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(false);
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

  const handleLogin = () => {
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
      <div className="fixed inset-0 bg-brand-dark flex flex-col lg:flex-row z-50 overflow-y-auto">
        {/* Left: immersive technical hero */}
        <div className="relative flex-1 lg:flex-[1.3] min-h-[300px] lg:min-h-0 hero-grid-bg flex flex-col justify-between p-8 lg:p-14 overflow-hidden">
          {/* depth vignette */}
          <div className="absolute inset-0 bg-gradient-to-br from-brand-dark via-brand-dark to-[#12294a] pointer-events-none" />
          <div className="login-ambient-glow login-ambient-glow-one" />
          <div className="login-ambient-glow login-ambient-glow-two" />

          {/* Diagram: captor + cono de protección + puesta a tierra */}
          <svg
            viewBox="0 0 320 460"
            className="login-diagram absolute right-[-6%] bottom-[-4%] w-[72%] max-w-sm lg:max-w-md opacity-95 pointer-events-none"
            fill="none"
          >
            {/* puesta a tierra: línea base */}
            <path
              d="M10,380 L140,380 L150,365 L160,395 L170,370 L180,380 L310,380"
              stroke="rgba(148,163,184,0.4)"
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
            />
            {/* puesta a tierra: pulso que recorre el conductor, en loop */}
            <path
              d="M10,380 L140,380 L150,365 L160,395 L170,370 L180,380 L310,380"
              stroke="#3d94e0"
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              className="ground-flow"
            />

            {/* zona de protección (cono / techo) */}
            <path
              d="M160,130 L40,260 M160,130 L280,260"
              stroke="rgba(226,232,240,0.5)"
              strokeWidth="2"
              strokeLinecap="round"
            />
            {/* muros */}
            <path
              d="M40,260 L40,380 M280,260 L280,380"
              stroke="rgba(226,232,240,0.35)"
              strokeWidth="1.5"
            />
            {/* puerta */}
            <path
              d="M140,380 L140,315 L180,315 L180,380"
              stroke="rgba(226,232,240,0.35)"
              strokeWidth="1.5"
            />

            {/* cuna del captor */}
            <path
              d="M152,131 a8,7 0 1,0 16,0"
              stroke="rgba(226,232,240,0.65)"
              strokeWidth="2"
              strokeLinecap="round"
            />

            {/* rayo: se dibuja una vez al cargar y luego late suavemente */}
            <g transform="translate(91.8,-6.4) scale(6.2)">
              <path
                d="M13 2 3 14h9l-1 8 10-12h-9l1-8z"
                stroke="#3d94e0"
                strokeWidth="0.35"
                strokeLinejoin="round"
                strokeLinecap="round"
                className="bolt-draw-icon"
              />
            </g>
          </svg>

          <div className="relative z-10 flex items-center gap-3">
            <div className="w-10 h-10 bg-brand-blue rounded flex items-center justify-center text-white shrink-0">
              <Zap className="w-6 h-6 fill-white icon-pulse" />
            </div>
            <div>
              <div className="font-condensed font-extrabold text-xl text-white tracking-wide">
                FARADYNE
              </div>
              <div className="text-[10px] text-slate-400 uppercase tracking-wider">
                Diseño y Cálculo de Pararrayos
              </div>
            </div>
          </div>

          <div className="login-message relative z-10 max-w-md mt-10 lg:mt-0">
            <h1 className="login-headline font-sans font-semibold tracking-[-0.035em] text-3xl lg:text-5xl text-white leading-[1.04] mb-4">
              Del plano al modelo 3D, con la precisión que exige la norma.
            </h1>
            <p className="login-copy text-sm text-slate-300 leading-relaxed max-w-sm">
              Nivel de protección, ubicación de mástiles y memoria descriptiva,
              en un mismo flujo de trabajo para el equipo de proyecto.
            </p>
          </div>

          <div className="relative z-10 flex flex-wrap gap-x-8 gap-y-4 mt-10 lg:mt-0">
            <div>
              <div className="font-condensed font-bold text-2xl text-white">IEC 62305</div>
              <div className="text-[11px] text-slate-400">Norma de referencia</div>
            </div>
            <div>
              <div className="font-condensed font-bold text-2xl text-white">I – IV</div>
              <div className="text-[11px] text-slate-400">Niveles de protección</div>
            </div>
            <div>
              <div className="font-condensed font-bold text-2xl text-white">3D</div>
              <div className="text-[11px] text-slate-400">Modelado de geometría</div>
            </div>
          </div>
        </div>

        {/* Right: login panel */}
        <div className="w-full lg:w-[400px] bg-white flex items-center justify-center p-6 lg:p-10 shrink-0">
          <div className="w-full max-w-sm animate-fade-in">
            <h2 className="font-condensed font-bold text-2xl text-brand-dark mb-1">
              Ingresar al sistema
            </h2>
            <p className="text-xs text-gray-500 mb-6">
              Accedé con tus credenciales de proyectista.
            </p>

            {false && <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
                  Usuario / Email
                </label>
                <div className="relative">
                  <input
                    type="text"
                    defaultValue="proyectista@faradyne.com"
                    className="input-electric w-full pl-9 pr-3 py-2 border border-gray-300 rounded text-xs"
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
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Ingresá tu contraseña"
                    className="input-electric w-full pl-9 pr-9 py-2 border border-gray-300 rounded text-xs"
                  />
                  <Lock className="w-4 h-4 text-gray-400 absolute left-2.5 top-2.5" />
                  <button
                    type="button"
                    onClick={() => setShowPassword((current) => !current)}
                    disabled={!password}
                    className="absolute right-2.5 top-2.5 text-gray-400 hover:text-brand-blue transition disabled:cursor-not-allowed disabled:opacity-40"
                    aria-label={showPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <button
                type="submit"
                className="btn-electric w-full py-2.5 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition flex items-center justify-center gap-1.5"
              >
                Ingresar al Sistema <ArrowRight className="w-4 h-4" />
              </button>
            </form>}
            <LoginForm onLogin={handleLogin} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`app-workspace min-h-screen bg-slate-100/70 flex flex-col font-sans ${isDarkMode ? 'dark-mode' : ''}`}>
      {/* Top Navbar Header */}
      <header className="header-grid-bg bg-slate-900 text-white h-12 px-5 flex items-center justify-between border-b border-slate-800 shadow-md">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-brand-blue fill-brand-blue icon-pulse" />
          <span className="font-condensed font-bold text-lg tracking-wider">FARADYNE</span>
          <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">
            v1.0.0
          </span>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-300">
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="text-slate-500">Proyecto:</span>
            <span className="bg-brand-blue/15 border border-brand-blue/40 text-white px-2.5 py-1 rounded-full font-semibold shadow-glow-sm">
              {projectData.nombre}
            </span>
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
      <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto overflow-hidden">
        <div key={currentStep} className="step-transition">
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
            idPlano={idPlano}          
            idModelo2D={idModelo2D} 
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
        </div>
      </main>
        
      <button
        type="button"
        onClick={() => setIsDarkMode((current) => !current)}
        className="theme-toggle fixed bottom-5 z-50 flex h-11 w-11 items-center justify-center rounded-full text-xs font-bold shadow-lg transition"
        aria-label={isDarkMode ? 'Activar modo claro' : 'Activar modo nocturno'}
        title={isDarkMode ? 'Cambiar a modo claro' : 'Cambiar a modo nocturno'}
      >
        {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      </button>
    </div>
  );
}

export default App;
