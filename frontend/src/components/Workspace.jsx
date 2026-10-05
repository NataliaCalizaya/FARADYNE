import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Zap, Moon, Sun, Loader2 } from 'lucide-react';

import { StepperBar } from './Stepper/StepperBar';
import { DatosProyecto } from '../pages/DatosProyecto';
import { CargarYValidarPlano } from '../pages/CargarYValidarPlano';
import { GenerarModelo3DPage } from '../pages/GenerarModelo3DPage';
import { NivelProteccion } from '../pages/NivelProteccion';
import { UbicacionMastiles } from '../pages/UbicacionMastiles';
import { ListadoMateriales } from '../pages/ListadoMateriales';
import { MemoriaDescriptiva } from '../pages/MemoriaDescriptiva';
import { proyectosApi } from '../api/proyectos';

// Slug ↔ índice de paso (debe coincidir con el orden de StepperBar.STEPS)
const STEP_SLUGS = ['datos', 'plano', 'modelo3d', 'nivel', 'mastiles', 'materiales', 'memoria'];

export function Workspace({ onLogout }) {
  const { idParam, paso } = useParams(); // /proyecto/:idParam/:paso
  const navigate = useNavigate();

  // ── Modo oscuro ─────────────────────────────────────────────────────────────
  const [isDarkMode, setIsDarkMode] = useState(false);

  // ── Estado del proyecto (reemplaza los useState de App.jsx) ─────────────────
  const [idProyecto, setIdProyecto]             = useState(null);
  const [idPlano, setIdPlano]                   = useState(null);
  const [idModelo2D, setIdModelo2D]             = useState(null);
  const [idModelo3D, setIdModelo3D]             = useState(null);
  const [isGeometriaValidada, setIsGeometriaValidada] = useState(false);
  const [projectData, setProjectData]           = useState({
    nombre: '', descripcion: '', ubicacion: '', departamento: '',
  });

  // true mientras carga el proyecto desde la URL (arranca en true si hay UUID en la URL)
  const [isLoading, setIsLoading] = useState(idParam !== 'nuevo');

  // Índice actual derivado del slug en la URL
  const currentStep = Math.max(0, STEP_SLUGS.indexOf(paso));

  // Navega al paso i — si todavía estamos en /nuevo usa el UUID real cuando ya lo tenemos
  const setCurrentStep = useCallback((i) => {
    const targetId = (idParam === 'nuevo' && idProyecto) ? idProyecto : idParam;
    navigate(`/proyecto/${targetId}/${STEP_SLUGS[i]}`);
  }, [navigate, idParam, idProyecto]);

  // ── Handlers (mismos que vivían en App.jsx) ─────────────────────────────────
  const handleProyectoCreado = (nuevoId, data) => {
    setIdProyecto(nuevoId);
    if (data) setProjectData((prev) => ({ ...prev, ...data }));
  };

  const handlePlanoUploaded = (planoData) => {
    if (!planoData) return;
    if (planoData.id)          setIdPlano(planoData.id);
    if (planoData.id_modelo2d) setIdModelo2D(planoData.id_modelo2d);
  };

  const handleGeometriaConfirmed = () => setIsGeometriaValidada(true);

  const handleModelo3DGenerated = (data) => {
    if (data?.id) setIdModelo3D(data.id);
  };

  const handleNivelCalculated = () => {};

  // ── Efecto 1: cargar proyecto desde la BD cuando el idParam es un UUID ──────
  useEffect(() => {
    if (idParam === 'nuevo') {
      // Sesión de proyecto nuevo: resetear todo
      setIdProyecto(null);
      setIdPlano(null);
      setIdModelo2D(null);
      setIdModelo3D(null);
      setIsGeometriaValidada(false);
      setProjectData({ nombre: '', descripcion: '', ubicacion: '', departamento: '' });
      return;
    }

    let cancelled = false;
    setIsLoading(true);
    proyectosApi.getProyectoCompleto(idParam)
      .then((data) => {
        if (cancelled) return;
        setIdProyecto(data.id_proyecto);
        setIdPlano(data.id_plano   || null);
        setIdModelo2D(data.id_modelo2d || null);
        setIdModelo3D(data.id_modelo3d || null);
        setIsGeometriaValidada(data.geometria_validada || false);
        setProjectData({
          nombre:      data.nombre      || '',
          descripcion: data.descripcion || '',
          ubicacion:   data.ubicacion   || '',
          departamento: data.departamento || '',
        });
      })
      .catch(() => { if (!cancelled) navigate('/'); })
      .finally(() => { if (!cancelled) setIsLoading(false); });

    return () => { cancelled = true; };
  }, [idParam]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Efecto 2: en /nuevo, una vez que llegue el UUID real, reemplazar la URL ─
  useEffect(() => {
    if (idParam === 'nuevo' && idProyecto) {
      navigate(`/proyecto/${idProyecto}/${paso}`, { replace: true });
    }
  }, [idProyecto]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Efecto 3: guard de pasos (solo tras cargar desde URL, no en flujo vivo) ─
  useEffect(() => {
    const stepIdx = STEP_SLUGS.indexOf(paso);
    if (stepIdx < 0) { navigate('/'); return; }

    if (idParam === 'nuevo') {
      // En /nuevo solo el paso 0 (datos) es válido sin proyecto creado
      if (stepIdx > 0) { navigate('/proyecto/nuevo/datos'); return; }
      return;
    }

    if (isLoading) return;
    // Paso 1+ requiere que exista un plano
    if (stepIdx >= 1 && !idPlano)   { navigate(`/proyecto/${idParam}/datos`);  return; }
    // Paso 2+ requiere que exista el modelo 3D
    if (stepIdx >= 2 && !idModelo3D){ navigate(`/proyecto/${idParam}/plano`);  return; }
  }, [isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Pantalla de carga ───────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-brand-dark flex items-center justify-center">
        <div className="flex items-center gap-3 text-white">
          <Loader2 className="w-6 h-6 animate-spin text-brand-blue" />
          <span className="font-condensed text-lg">Cargando proyecto…</span>
        </div>
      </div>
    );
  }

  // ── Layout autenticado (extraído de App.jsx sin cambios visuales) ───────────
  return (
    <div className={`app-workspace min-h-screen bg-slate-100/70 flex flex-col font-sans ${isDarkMode ? 'dark-mode' : ''}`}>

      {/* Top Navbar Header */}
      <header className="header-grid-bg bg-slate-900 text-white h-12 px-5 flex items-center justify-between border-b border-slate-800 shadow-md">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-brand-blue fill-brand-blue icon-pulse" />
          <span className="font-condensed font-bold text-lg tracking-wider">FARADYNE</span>
          <span className="text-[10px] bg-slate-800 text-slate-400 px-2 py-0.5 rounded font-mono">v1.0.0</span>
        </div>

        <div className="flex items-center gap-4 text-xs text-slate-300">
          <div className="hidden sm:flex items-center gap-1.5">
            <span className="text-slate-500">Proyecto:</span>
            <span className="bg-brand-blue/15 border border-brand-blue/40 text-white px-2.5 py-1 rounded-full font-semibold shadow-glow-sm">
              {projectData.nombre}
            </span>
          </div>
          <button
            onClick={onLogout}
            className="text-slate-400 hover:text-white text-[11px] underline"
          >
            Cerrar sesión
          </button>
        </div>
      </header>

      {/* Stepper Progress Bar */}
      <StepperBar
        currentStep={currentStep}
        onStepChange={setCurrentStep}
        isGeometriaValidada={isGeometriaValidada}
      />

      {/* Page Content Viewport */}
      <main className="flex-1 p-4 md:p-6 max-w-7xl w-full mx-auto overflow-hidden">
        <div key={currentStep} className="step-transition">
          {currentStep === 0 && (
            <DatosProyecto
              projectData={projectData}
              setProjectData={setProjectData}
              idProyecto={idProyecto}
              onProyectoCreado={handleProyectoCreado}
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
              onModelo3DGenerated={handleModelo3DGenerated}
              onBack={() => setCurrentStep(1)}
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
            <MemoriaDescriptiva projectData={projectData} idProyecto={idProyecto} />
          )}
        </div>
      </main>

      {/* Botón de tema */}
      <button
        type="button"
        onClick={() => setIsDarkMode((c) => !c)}
        className="theme-toggle fixed bottom-5 z-50 flex h-11 w-11 items-center justify-center rounded-full text-xs font-bold shadow-lg transition"
        aria-label={isDarkMode ? 'Activar modo claro' : 'Activar modo nocturno'}
        title={isDarkMode ? 'Cambiar a modo claro' : 'Cambiar a modo nocturno'}
      >
        {isDarkMode ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
      </button>
    </div>
  );
}

export default Workspace;
