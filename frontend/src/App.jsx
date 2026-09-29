import React, { useState } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Workspace } from './components/Workspace';
import { LoginForm } from './components/auth/LoginForm';
import { Zap } from 'lucide-react';

// Clave de localStorage para persistir la sesión entre recargas
const AUTH_KEY = 'faradyne_auth';

export function App() {
  // Inicializa desde localStorage para que F5 no vuelva al login
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => localStorage.getItem(AUTH_KEY) === 'true'
  );

  const handleLogin = () => {
    localStorage.setItem(AUTH_KEY, 'true');
    setIsAuthenticated(true);
    // La URL del browser no cambia: si el usuario llegó a /proyecto/uuid/paso,
    // al autenticarse el router lo lleva directo a ese Workspace.
  };

  const handleLogout = () => {
    localStorage.removeItem(AUTH_KEY);
    setIsAuthenticated(false);
  };

  // ── Pantalla de login (sin cambios visuales respecto al original) ───────────
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
            <LoginForm onLogin={handleLogin} />
          </div>
        </div>
      </div>
    );
  }

  // ── Rutas autenticadas ──────────────────────────────────────────────────────
  return (
    <Routes>
      {/* Redirige la raíz a un proyecto nuevo en el paso inicial */}
      <Route path="/" element={<Navigate to="/proyecto/nuevo/datos" replace />} />
      {/* Conveniencia: /proyecto/nuevo → /proyecto/nuevo/datos */}
      <Route path="/proyecto/nuevo" element={<Navigate to="/proyecto/nuevo/datos" replace />} />
      {/* Ruta principal: proyecto existente o nuevo, cualquier paso */}
      <Route path="/proyecto/:idParam/:paso" element={<Workspace onLogout={handleLogout} />} />
      {/* Catch-all: cualquier URL desconocida vuelve a la raíz */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
