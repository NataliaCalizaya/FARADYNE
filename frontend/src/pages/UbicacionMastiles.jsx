import React, { useState, useEffect, useCallback } from 'react';
import { Info, MapPin, Box, Loader2, AlertTriangle } from 'lucide-react';

import { GeometriaViewerMastiles } from '../components/GeometriaViewerMastiles/GeometriaViewerMastiles';
import { MastilPositioner } from '../components/MastilPositioner/MastilPositioner';
import { Modelo3DViewer } from '../components/Modelo3DViewer/Modelo3DViewer';
import { planosApi } from '../api/planos';
import { mastilesApi } from '../api/mastiles';
import { modelos3dApi } from '../api/modelos3d';
import { getMastColor } from '../api/utilsMastilVisual';

/**
 * UbicacionMastiles (HU05 + HU03)
 *
 * Flujo:
 *  1. Carga el Modelo 2D validado desde el backend.
 *  2. Muestra GeometriaViewerMastiles (visor 2D solo-lectura, con clic para
 *     colocar mástiles, y arrastre para moverlos).
 *  3. Muestra MastilPositioner (panel lateral: altura del próximo mástil,
 *     leyenda de colores, lista de mástiles y edición del seleccionado).
 *  4. Clic en geometría → modal de confirmación → POST /mastiles → lista
 *     actualizada. Persistencia inmediata: cada alta/baja/edición se guarda
 *     en el momento (no hay un botón de "guardar todo" separado), y queda
 *     asociada al proyecto vía id_proyecto.
 *  5. Modelo3DViewer se re-renderiza automáticamente ante cualquier cambio
 *     de `masts` (alta, baja, mover, cambiar altura), porque ese estado es
 *     la única fuente de verdad y se le pasa como prop.
 *
 * Vista "2D + 3D": ambos visores se muestran EN PARALELO (uno junto al
 * otro), no apilados verticalmente.
 */
export const UbicacionMastiles = ({
  idProyecto,
  idModelo3D: idModelo3DProp,
  idModelo2D,
  idPlano,
  onNext,
}) => {
  // ── Estado principal ─────────────────────────────────────────────
  const [idModelo3D, setIdModelo3D] = useState(idModelo3DProp || null);
  const [masts, setMasts] = useState([]);
  const [coverageData, setCoverageData] = useState(null);

  // ── UI ───────────────────────────────────────────────────────────
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [placing, setPlacing] = useState(false);
  const [mastHeight, setMastHeight] = useState(1.0);
  const [viewMode, setViewMode] = useState('split'); // 'split' | '2d' | '3d'
  const [saving, setSaving] = useState(false);

  // Mástil actualmente seleccionado (para editar altura / eliminar / mover).
  const [selectedMastId, setSelectedMastId] = useState(null);

  // Coordenadas pendientes de confirmación (alta de un mástil nuevo).
  const [pendingCoords, setPendingCoords] = useState(null);

  // ── Efectivo idModelo2D (puede venir como prop o resolverse desde idPlano) ──
  const [resolvedModelo2DId, setResolvedModelo2DId] = useState(idModelo2D || null);


  // ── Carga inicial ────────────────────────────────────────────────

  const resolveModelo2D = useCallback(async () => {
    // Si idModelo2D ya está disponible como prop, usarlo directamente.
    if (idModelo2D) {
      setResolvedModelo2DId(idModelo2D);
      return idModelo2D;
    }

    // Si viene solo idPlano, obtener el Modelo 2D desde la preview del plano.
    if (idPlano) {
      try {
        const preview = await planosApi.getPlanoPreview(idPlano);
        const m2dId = preview?.id_modelo2d || preview?.id;
        if (m2dId) {
          setResolvedModelo2DId(m2dId);
          return m2dId;
        }
      } catch (err) {
        console.warn('[UbicacionMastiles] No se pudo resolver Modelo 2D desde plano:', err);
      }
    }

    return null;
  }, [idModelo2D, idPlano]);

  const resolveModelo3D = useCallback(async (m2dId) => {
    // Si ya tenemos el id como prop, usarlo.
    if (idModelo3DProp) {
      setIdModelo3D(idModelo3DProp);
      return idModelo3DProp;
    }

    if (!m2dId) return null;

    try {
      // Intentar obtener el Modelo 3D existente por Modelo 2D.
      // OJO: el backend devuelve la clave `id_modelo3d` (no `id`), igual que
      // en el resto de las respuestas (id_modelo2d, id_proyecto, etc.). Si
      // solo se chequea `.id` acá, nunca se detecta que ya existe un
      // Modelo3D y se termina regenerando uno nuevo en cada visita a la
      // página, perdiendo la asociación con los mástiles ya guardados.
      const existing = await modelos3dApi.getModelo3DByModelo2D(m2dId).catch(() => null);
      const existingId = existing?.id_modelo3d || existing?.id || null;
      if (existingId) {
        setIdModelo3D(existingId);
        return existingId;
      }

      // Si no existe, generarlo.
      try {
        const generated = await modelos3dApi.generateModelo3D({ id_modelo2d: m2dId });
        const id = generated?.id_modelo3d || generated?.id || null;
        setIdModelo3D(id);
        return id;
      } catch (genErr) {
        // Puede fallar porque, por una carrera (doble llamada, doble
        // pestaña, etc.), el Modelo3D ya fue creado justo antes. En vez de
        // perder la referencia, reintentamos obtenerlo en lugar de generar.
        console.warn('[UbicacionMastiles] Falló generar Modelo3D, reintentando obtener el existente:', genErr);
        const retry = await modelos3dApi.getModelo3DByModelo2D(m2dId).catch(() => null);
        const retryId = retry?.id_modelo3d || retry?.id || null;
        if (retryId) {
          setIdModelo3D(retryId);
          return retryId;
        }
        throw genErr;
      }

    } catch (err) {
      console.warn('[UbicacionMastiles] No se pudo resolver Modelo 3D:', err);
      return null;
    }
  }, [idModelo3DProp]);

  const loadMasts = useCallback(async (modelo3dId) => {
    if (!modelo3dId) return;
    try {
      const data = await mastilesApi.getMastilesByModelo3D(modelo3dId);
      setMasts(Array.isArray(data) ? data : []);
    } catch (err) {
      console.warn('[UbicacionMastiles] No se pudieron cargar los mástiles:', err);
    }
  }, []);

  const loadCoverage = useCallback(async () => {
    if (!idProyecto) return;
    try {
      const data = await mastilesApi.getCobertura(idProyecto);
      setCoverageData(data);
    } catch (err) {
      console.warn('[UbicacionMastiles] No se pudo cargar cobertura:', err);
    }
  }, [idProyecto]);

  // Inicialización completa
  useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const m2dId = await resolveModelo2D();
        if (cancelled) return;

        if (!m2dId) {
          // Un 3D ya existente puede consultarse sin abrir el editor 2D.
          // Para crear o ubicar mástiles, en cambio, el Modelo 2D es obligatorio.
          if (idModelo3DProp) {
            setIdModelo3D(idModelo3DProp);
            await loadMasts(idModelo3DProp);
            await loadCoverage();
            setError('No se encontró el Modelo 2D. Se muestra el Modelo 3D disponible, pero para ubicar mástiles debe completar el paso de geometría.');
          } else {
            setError('No se encontró el Modelo 2D. Asegúrese de haber completado el paso anterior.');
          }
          return;
        }

        const m3dId = await resolveModelo3D(m2dId);
        if (cancelled) return;

        if (m3dId) {
          await loadMasts(m3dId);
          await loadCoverage();
        }

      } catch (err) {
        if (!cancelled) {
          setError('Error al inicializar la página. Recargue e intente nuevamente.');
          console.error('[UbicacionMastiles] Error de inicialización:', err);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [resolveModelo2D, resolveModelo3D, loadMasts, loadCoverage]);


  // ── Handlers de colocación ───────────────────────────────────────

  /**
   * Llamado por GeometriaViewerMastiles cuando el usuario hace clic
   * en la geometría 2D (con placing=true).
   */
  const handleMastClick = useCallback((x, y) => {
    if (!placing) return;
    setPendingCoords({ x, y });
    setPlacing(false);
  }, [placing]);

  /** Confirmar colocación del mástil y persistir en el backend. */
  const handleConfirmMast = async () => {
    if (!pendingCoords) return;

    setSaving(true);
    setError(null);

    try {
      const newMast = await mastilesApi.createMastil({
        id_modelo3d: idModelo3D || undefined,
        id_modelo2d: !idModelo3D ? resolvedModelo2DId : undefined,
        id_proyecto: idProyecto,
        posicion_x: pendingCoords.x,
        posicion_y: pendingCoords.y,
        posicion_z: 0,
        altura: mastHeight,
        tipo: 'Franklin',
      });

      // Nueva referencia de array: dispara el re-render automático del
      // Modelo3DViewer (recibe `masts` como prop) sin ninguna otra acción.
      setMasts((prev) => [...prev, newMast]);
      setPendingCoords(null);
      setSelectedMastId(newMast?.id ?? null);

      // Actualizar cobertura en segundo plano
      loadCoverage();

    } catch (err) {
      console.error('[UbicacionMastiles] Error creando mástil:', err);
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'No se pudo guardar el mástil.');
      setPendingCoords(null);
    } finally {
      setSaving(false);
    }
  };


  // ── Handlers de edición (eliminar / mover / cambiar altura) ──────

  const handleDeleteMast = async (id) => {
    try {
      await mastilesApi.deleteMastil(id);
      setMasts((prev) => prev.filter((m) => m.id !== id));
      if (selectedMastId === id) setSelectedMastId(null);
      loadCoverage();
    } catch (err) {
      console.error('[UbicacionMastiles] Error eliminando mástil:', err);
      setError('No se pudo eliminar el mástil.');
    }
  };

  /** Arrastre de un mástil ya colocado en el visor 2D: guarda su nueva posición. */
  const handleMoveMast = async (id, x, y) => {
    // Optimista: refleja el movimiento de inmediato en ambos visores.
    setMasts((prev) =>
      prev.map((m) => (m.id === id ? { ...m, posicion_x: x, posicion_y: y } : m))
    );

    try {
      const updated = await mastilesApi.updateMastil(id, {
        posicion_x: x,
        posicion_y: y,
      });
      setMasts((prev) => prev.map((m) => (m.id === id ? updated : m)));
      loadCoverage();
    } catch (err) {
      console.error('[UbicacionMastiles] Error moviendo mástil:', err);
      setError('No se pudo guardar la nueva posición del mástil.');
      // Revertir recargando desde el backend ante un error de guardado.
      if (idModelo3D) loadMasts(idModelo3D);
    }
  };

  /** Cambiar la altura de un mástil ya colocado (desde el panel lateral). */
  const handleUpdateMastHeight = async (id, altura) => {
    try {
      const updated = await mastilesApi.updateMastil(id, { altura });
      setMasts((prev) => prev.map((m) => (m.id === id ? updated : m)));
      loadCoverage();
    } catch (err) {
      console.error('[UbicacionMastiles] Error actualizando altura:', err);
      setError('No se pudo actualizar la altura del mástil.');
    }
  };

  const handleSelectMast = (mast) => {
    setSelectedMastId(mast ? mast.id : null);
  };

  // Cancelar con Escape
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setPlacing(false);
        setPendingCoords(null);
        setSelectedMastId(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);


  // ── Render ────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
        <span className="text-sm">Cargando datos del proyecto...</span>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* ── Título ── */}
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900" >
        Ubicación de Mástiles Captores
      </h1>

      {/* ── Descripción del paso ── */}
      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 5 (HU05):</strong> Haga clic sobre el visor 2D para colocar mástiles
          pararrayos. Seleccione la altura en el panel derecho antes de colocar cada mástil.
          Puede arrastrar un mástil para moverlo, o seleccionarlo en la lista para cambiar su
          altura o eliminarlo. Los cambios se persisten automáticamente en el proyecto.
        </div>
      </div>

      {/* ── Error global ── */}
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-center gap-2 text-xs">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* ── Modal de confirmación de mástil nuevo ── */}
      {pendingCoords && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-gray-300 rounded-lg p-5 w-full max-w-xs shadow-2xl space-y-4">
            <div className="border-b border-gray-100 pb-2">
              <h3 className="font-condensed font-bold text-sm text-slate-900 uppercase">
                Confirmar Mástil
              </h3>
              <p className="text-[11px] text-gray-500 mt-1 flex items-center gap-1.5">
                <span
                  className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ backgroundColor: getMastColor(mastHeight) }}
                />
                Coordenadas: ({Number(pendingCoords.x).toFixed(2)},{' '}
                {Number(pendingCoords.y).toFixed(2)}) · Altura: {mastHeight} m · Tipo: Franklin
              </p>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={() => setPendingCoords(null)}
                className="flex-1 py-1.5 border border-red-500 text-red-600 hover:bg-red-50 rounded font-semibold text-xs transition"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleConfirmMast}
                disabled={saving}
                className="flex-1 py-1.5 bg-brand-blue hover:bg-brand-hover text-white rounded font-semibold text-xs transition disabled:opacity-60 flex items-center justify-center gap-1"
              >
                {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {saving ? 'Guardando...' : 'Colocar Mástil'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Métricas de resumen ── */}
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="grid grid-cols-3 gap-6 text-xs flex-1">
          <div>
            <div className="text-gray-500 font-medium">Radio Esfera Rodante (R)</div>
            <div className="text-xl font-bold text-brand-blue font-condensed">
              {coverageData?.radio_esfera_rodante_r ?? 30} m
            </div>
          </div>
          <div>
            <div className="text-gray-500 font-medium">Mástiles Instalados</div>
            <div className="text-xl font-bold text-gray-800 font-condensed">
              {masts.length}
            </div>
          </div>
          <div>
            <div className="text-gray-500 font-medium">Cobertura SPDA</div>
            <div className="text-xl font-bold text-emerald-600 font-condensed">
              {coverageData?.porcentaje_cobertura != null
                ? `${coverageData.porcentaje_cobertura}%`
                : masts.length > 0 ? '—' : '0%'}
            </div>
          </div>
        </div>

        {/* Selector de vista */}
        <div className="bg-slate-100 p-1 rounded-md border border-slate-200 flex items-center gap-1 shrink-0">
          {[
            { key: 'split', label: '2D + 3D' },
            { key: '2d', label: 'Solo 2D' },
            { key: '3d', label: 'Solo 3D' },
          ].map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setViewMode(key)}
              className={`px-3 py-1 rounded text-xs font-semibold transition ${
                viewMode === key ? 'bg-brand-blue text-white shadow' : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Visores: ocupan el ancho completo para que no se compriman ── */}
      <div>
        {/* split en 2 columnas SOLO si el viewer 3D está disponible */}
        <div
          className={
            viewMode === 'split' && idModelo3D && resolvedModelo2DId
              ? 'grid grid-cols-1 lg:grid-cols-2 gap-4 min-w-0 items-start'
              : 'flex flex-col gap-4 min-w-0'
          }
        >

          {/* GeometriaViewerMastiles */}
          {(viewMode === 'split' || viewMode === '2d') && (
            <div className="bg-white border border-gray-200 rounded-md shadow-sm p-3 min-w-0">
              <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
                <span className="text-xs font-bold text-gray-600 uppercase">
                  Vista 2D — Geometría Validada
                </span>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedMastId(null);
                    setPlacing((p) => !p);
                  }}
                  disabled={!resolvedModelo2DId}
                  className={`flex items-center gap-1.5 px-4 py-1.5 rounded font-bold text-xs transition disabled:opacity-50 ${
                    placing
                      ? 'bg-amber-500 hover:bg-amber-600 text-white'
                      : 'bg-brand-blue hover:bg-brand-hover text-white'
                  }`}
                >
                  <MapPin className="w-3.5 h-3.5" />
                  {placing ? 'Cancelar (Esc)' : `Colocar Mástil · ${mastHeight} m`}
                </button>
              </div>

              {resolvedModelo2DId ? (
                <GeometriaViewerMastiles
                  idModelo2D={resolvedModelo2DId}
                  masts={masts}
                  onMastClick={handleMastClick}
                  onMastMove={handleMoveMast}
                  onSelectMast={handleSelectMast}
                  selectedMastId={selectedMastId}
                  placing={placing}
                />
              ) : (
                <div className="py-10 text-center text-gray-400 text-xs">
                  No se pudo determinar el Modelo 2D.
                </div>
              )}
            </div>
          )}

          {/* Modelo 3D Viewer */}
          {(viewMode === 'split' || viewMode === '3d') && idModelo3D && (
            <div className={viewMode === 'split' ? 'h-[560px] min-w-0' : 'h-[560px]'}>
              <Modelo3DViewer
                idModelo3D={idModelo3D}
                idModelo2D={resolvedModelo2DId}
                masts={masts}
              />
            </div>
          )}
        </div>
      </div>

      {/* ── Datos y controles debajo, en dos columnas ── */}
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
        <MastilPositioner
          masts={masts}
          mastHeight={mastHeight}
          onHeightChange={setMastHeight}
          onDeleteMast={handleDeleteMast}
          onSelectMast={handleSelectMast}
          selectedMastId={selectedMastId}
          onUpdateMastHeight={handleUpdateMastHeight}
          onDeselectMast={() => setSelectedMastId(null)}
          coverageData={coverageData}
          placing={placing}
          onCancelPlace={() => setPlacing(false)}
        />
      </div>
      <button
        type="button"
        onClick={onNext}
        className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-xs transition flex items-center justify-center gap-2"
      >
        <Box className="w-4 h-4" />
        Confirmar Ubicación → Continuar
      </button>
    </div>
  );
};

export default UbicacionMastiles;