import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Info, MapPin, Box, Loader2, AlertTriangle, ChevronDown, ChevronUp,
  Trash2, Minus, Plus, X, Lightbulb,
} from 'lucide-react';

import { GeometriaViewerMastiles } from '../components/GeometriaViewerMastiles/GeometriaViewerMastiles';
import { Modelo3DViewer } from '../components/Modelo3DViewer/Modelo3DViewer';
import { RecomendacionesMastiles } from '../components/GeometriaViewerMastiles/RecomendacionesMastiles';
import { ResumenUbicacion } from '../components/GeometriaViewerMastiles/ResumenUbicacion';
import { planosApi } from '../api/planos';
import { mastilesApi } from '../api/mastiles';
import { modelos3dApi } from '../api/modelos3d';
import { getMastColor } from '../hooks/utilsMastilVisual';

// ============================================================
// CONSTANTES Y HELPERS
// ============================================================

// Rango y atajos de altura (m). Ajustar si el backend admite otros valores.
const MIN_H = 0.5;
const MAX_H = 30;
const STEP_H = 0.5;
const PRESETS = [0.5, 1, 1.5, 2, 2.5];

const ESTADO_PRISMA = {
  protegido: { label: 'Protegido', cls: 'text-emerald-600', dot: 'bg-emerald-500' },
  parcial: { label: 'Parcial', cls: 'text-amber-600', dot: 'bg-amber-500' },
  desprotegido: { label: 'Desprotegido', cls: 'text-red-600', dot: 'bg-red-500' },
};

const fmtNum = (v, d = 1) => (Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—');
const sameId = (a, b) => String(a) === String(b);
const clampH = (v) => Math.min(MAX_H, Math.max(MIN_H, Math.round(v * 100) / 100));

// Motivos por los que una terna no admite esfera (códigos del backend).
const MOTIVOS = {
  sin_esfera_toca_cubierta: {
    titulo: 'La esfera toca la cubierta',
    ayuda: 'Suba la altura de estos mástiles o reubíquelos.',
  },
  sin_esfera_radio_insuficiente: {
    titulo: 'Radio insuficiente',
    ayuda: 'Están demasiado separados para el radio R: acérquelos.',
  },
};

const motivoInfo = (codigo) =>
  MOTIVOS[codigo] || {
    titulo: codigo
      ? String(codigo).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase())
      : 'Otros motivos',
    ayuda: null,
  };

// La forma exacta de cada terna depende del backend: se leen los mástiles que
// la forman (por id) y se resuelven contra la lista actual.
const ternaInfo = (t, masts) => {
  const raw = Array.isArray(t)
    ? t
    : t?.mastiles ?? t?.ids_mastiles ?? t?.mastiles_ids ?? t?.ids ?? t?.indices ?? t?.puntas ?? null;

  const items = Array.isArray(raw)
    ? raw.map((r) => {
      const id = r && typeof r === 'object' ? (r.id ?? r.id_mastil) : r;
      const i = masts.findIndex((m) => sameId(m.id, id));
      return { id, mast: i >= 0 ? masts[i] : null, n: i + 1 };
    })
    : [];

  const motivo = t && typeof t === 'object' && !Array.isArray(t)
    ? (t.motivo ?? t.razon ?? t.mensaje ?? null)
    : null;

  return { items, motivo };
};


// ============================================================
// CONTROL DE ALTURA (presets + stepper + valor escrito)
// ============================================================

const HeightControl = ({ value, onChange }) => {
  const [text, setText] = useState(String(value));

  useEffect(() => {
    setText(String(value));
  }, [value]);

  const apply = (n) => {
    const next = clampH(n);
    if (Math.abs(next - value) > 1e-6) onChange(next);
    else setText(String(value));
  };

  const commitText = () => {
    const n = Number(String(text).replace(',', '.'));
    if (Number.isFinite(n) && n > 0) apply(n);
    else setText(String(value));
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex items-center gap-1">
        {PRESETS.map((p) => {
          const active = Math.abs(value - p) < 1e-6;
          return (
            <button
              key={p}
              type="button"
              onClick={() => apply(p)}
              title={`${p} m`}
              aria-pressed={active}
              className={`flex items-center gap-1 px-2 py-1 rounded-full border text-[11px] font-semibold transition ${active
                ? 'bg-slate-800 border-slate-800 text-white'
                : 'bg-white border-gray-300 text-gray-700 hover:border-brand-blue hover:text-brand-blue'
                }`}
            >
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ backgroundColor: getMastColor(p) }}
              />
              {p} m
            </button>
          );
        })}
      </div>

      <div className="flex items-center border border-gray-300 rounded-md bg-white overflow-hidden">
        <button
          type="button"
          onClick={() => apply(value - STEP_H)}
          disabled={value <= MIN_H}
          className="px-2 py-1.5 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
          aria-label="Bajar altura"
        >
          <Minus className="w-3.5 h-3.5" />
        </button>
        <input
          type="text"
          inputMode="decimal"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={commitText}
          onKeyDown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur();
            if (e.key === 'Escape') setText(String(value));
          }}
          className="w-12 text-center text-xs font-semibold tabular-nums outline-none py-1"
          aria-label="Altura en metros"
        />
        <span className="text-[11px] text-gray-400 pr-1">m</span>
        <button
          type="button"
          onClick={() => apply(value + STEP_H)}
          disabled={value >= MAX_H}
          className="px-2 py-1.5 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
          aria-label="Subir altura"
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
};


// ============================================================
// PANELES INFERIORES
// ============================================================

const Panel = ({ title, count, children }) => (
  <section className="bg-white border border-gray-200 rounded-md shadow-sm min-w-0 flex flex-col">
    <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-gray-100">
      <h3 className="text-[11px] font-bold uppercase text-gray-600">{title}</h3>
      {count != null && (
        <span className="px-1.5 py-0.5 rounded-full bg-gray-100 text-[10px] font-semibold text-gray-600">
          {count}
        </span>
      )}
    </header>
    <div className="p-2 max-h-72 overflow-y-auto text-xs text-slate-700">{children}</div>
  </section>
);

const PanelMastiles = ({ masts, selectedMastId, onSelect, onDelete }) => (
  <Panel title="Mástiles instalados" count={masts.length}>
    {masts.length === 0 ? (
      <p className="py-4 text-center text-gray-400">Aún no hay mástiles colocados.</p>
    ) : (
      <ul className="space-y-0.5">
        {masts.map((m, i) => {
          const selected = sameId(m.id, selectedMastId);
          return (
            <li key={m.id ?? i} className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => onSelect(selected ? null : m)}
                className={`flex-1 min-w-0 flex items-center gap-2 px-2 py-1.5 rounded text-left transition ${selected ? 'bg-fuchsia-50 ring-1 ring-fuchsia-300' : 'hover:bg-gray-50'
                  }`}
              >
                <span
                  className="w-5 h-5 rounded-full shrink-0 flex items-center justify-center text-[9px] font-bold text-white"
                  style={{ backgroundColor: getMastColor(m.altura) }}
                >
                  {i + 1}
                </span>
                <span className="flex-1 min-w-0 truncate tabular-nums text-gray-500">
                  {fmtNum(m.posicion_x, 2)}, {fmtNum(m.posicion_y, 2)}
                </span>
                <span className="shrink-0 font-semibold tabular-nums">{fmtNum(m.altura, 1)} m</span>
              </button>
              <button
                type="button"
                onClick={() => onDelete(m.id)}
                title="Eliminar mástil"
                aria-label={`Eliminar mástil ${i + 1}`}
                className="p-1.5 rounded text-gray-400 hover:text-red-600 hover:bg-red-50 transition"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          );
        })}
      </ul>
    )}
  </Panel>
);

// Mini tarjeta de un mástil dentro de una terna.
const MastChip = ({ item, onSelect }) => {
  if (!item.mast) {
    // Mástil que ya no está en la lista (p. ej. eliminado): cobertura desactualizada.
    return (
      <span
        title="Este mástil ya no está en la lista; actualice la cobertura"
        className="inline-flex items-center px-1.5 py-1 rounded-md border border-dashed border-gray-300 bg-gray-50 text-[11px] font-semibold text-gray-400 tabular-nums"
      >
        {String(item.id)}
      </span>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onSelect?.(item.mast)}
      title={`Mástil ${item.n} · ${fmtNum(item.mast.altura, 1)} m`}
      className="inline-flex items-center gap-1 px-1.5 py-1 rounded-md border border-gray-200 bg-white text-[11px] font-bold text-slate-700 hover:border-brand-blue hover:text-brand-blue transition"
    >
      <span
        className="inline-block w-2 h-2 rounded-full"
        style={{ backgroundColor: getMastColor(item.mast.altura) }}
      />
      #{item.n}
    </button>
  );
};

const PanelTernas = ({ coverageData, masts, onSelect }) => {
  const ternas = coverageData?.triangulos_sin_esfera || [];

  // Agrupadas por motivo: una columna por cada uno.
  const grupos = [];
  ternas.forEach((t, i) => {
    const info = ternaInfo(t, masts);
    const key = info.motivo || 'otros';
    let g = grupos.find((x) => x.key === key);
    if (!g) {
      g = { key, ...motivoInfo(info.motivo), ternas: [] };
      grupos.push(g);
    }
    g.ternas.push({ n: i + 1, items: info.items });
  });

  return (
    <Panel title="Ternas sin esfera posible" count={coverageData ? ternas.length : null}>
      {!coverageData ? (
        <p className="py-4 text-center text-gray-400">Sin datos de cobertura todavía.</p>
      ) : ternas.length === 0 ? (
        <p className="py-4 text-center text-emerald-600 font-semibold">
          Todas las ternas admiten esfera rodante.
        </p>
      ) : (
        <div
          className="grid gap-3"
          style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))' }}
        >
          {grupos.map((g) => (
            <div key={g.key} className="min-w-0 rounded-md border border-amber-200 bg-amber-50/60">
              <div className="px-2.5 py-1.5 border-b border-amber-200">
                <p className="flex items-center justify-between gap-2 font-bold text-amber-800">
                  <span className="truncate">{g.titulo}</span>
                  <span className="shrink-0 px-1.5 rounded-full bg-amber-200/70 text-[10px]">
                    {g.ternas.length}
                  </span>
                </p>
                {g.ayuda && <p className="text-[10px] text-amber-700 mt-0.5">{g.ayuda}</p>}
              </div>

              <ul className="p-2 space-y-1.5">
                {g.ternas.map((t) => (
                  <li key={t.n} className="flex flex-wrap items-center gap-1">
                    <span className="w-12 shrink-0 text-[10px] font-semibold text-amber-700 uppercase">
                      Terna {t.n}
                    </span>
                    {t.items.map((it, k) => (
                      <MastChip key={`${t.n}-${k}`} item={it} onSelect={onSelect} />
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
};

const PanelCubiertas = ({ coverageData }) => {
  const prismas = coverageData?.prismas || [];
  const advertencias = coverageData?.advertencias || [];

  return (
    <Panel title="Cobertura por cubierta" count={coverageData ? prismas.length : null}>
      {!coverageData ? (
        <p className="py-4 text-center text-gray-400">Sin datos de cobertura todavía.</p>
      ) : (
        <div className="space-y-2">
          {advertencias.map((a, i) => (
            <p
              key={i}
              className="flex gap-1.5 text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5"
            >
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
              <span className="min-w-0 break-words">{a}</span>
            </p>
          ))}

          <ul className="space-y-1">
            {prismas.map((p) => {
              const est = ESTADO_PRISMA[p.estado] || {
                label: p.estado, cls: 'text-slate-500', dot: 'bg-slate-400',
              };
              return (
                <li key={p.id} className="flex items-center justify-between gap-2 min-w-0">
                  <span className="flex items-center gap-1.5 min-w-0">
                    <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${est.dot}`} />
                    <span className="truncate">{p.id}</span>
                  </span>
                  <span className={`shrink-0 font-semibold ${est.cls}`}>
                    {est.label} · {fmtNum(p.porcentaje_cobertura, 0)} %
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Panel>
  );
};


// ============================================================
// PÁGINA
// ============================================================

/**
 * UbicacionMastiles (HU05 + HU03)
 *
 * - Barra superior única: colocar mástil + altura. Si hay un mástil
 *   seleccionado, el mismo control edita SU altura; si no, fija la altura del
 *   próximo mástil.
 * - Colocar es directo: un clic en el visor 2D crea el mástil (sin modal) y la
 *   herramienta sigue activa hasta pulsar Esc o el botón.
 * - Debajo de los visores: mástiles instalados, ternas sin esfera y cobertura
 *   por cubierta.
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
  const [showRecs, setShowRecs] = useState(false);
  const [selectedMastId, setSelectedMastId] = useState(null);

  const [resolvedModelo2DId, setResolvedModelo2DId] = useState(idModelo2D || null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const creatingRef = useRef(false);
  const heightTimers = useRef({});

  // ── Carga inicial ────────────────────────────────────────────────

  const resolveModelo2D = useCallback(async () => {
    if (idModelo2D) {
      setResolvedModelo2DId(idModelo2D);
      return idModelo2D;
    }

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
    if (idModelo3DProp) {
      setIdModelo3D(idModelo3DProp);
      return idModelo3DProp;
    }

    if (!m2dId) return null;

    try {
      // El backend devuelve `id_modelo3d` (no `id`): si solo se mirara `.id`
      // nunca se detectaría el Modelo 3D existente y se regeneraría en cada visita.
      const existing = await modelos3dApi.getModelo3DByModelo2D(m2dId).catch(() => null);
      const existingId = existing?.id_modelo3d || existing?.id || null;
      if (existingId) {
        setIdModelo3D(existingId);
        return existingId;
      }

      try {
        const generated = await modelos3dApi.generateModelo3D({ id_modelo2d: m2dId });
        const id = generated?.id_modelo3d || generated?.id || null;
        setIdModelo3D(id);
        return id;
      } catch (genErr) {
        // Posible carrera (doble llamada): reintentar obtener el existente.
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

  const coverageReq = useRef(0);

  const loadCoverage = useCallback(async () => {
    if (!idProyecto) return;
    const id = ++coverageReq.current;
    setCoverageLoading(true);
    try {
      const data = await mastilesApi.getCobertura(idProyecto);
      if (id === coverageReq.current) setCoverageData(data);
    } catch (err) {
      console.warn('[UbicacionMastiles] No se pudo cargar cobertura:', err);
    } finally {
      if (id === coverageReq.current) setCoverageLoading(false);
    }
  }, [idProyecto]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      setLoading(true);
      setError(null);

      try {
        const m2dId = await resolveModelo2D();
        if (cancelled) return;

        if (!m2dId) {
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
  }, [resolveModelo2D, resolveModelo3D, loadMasts, loadCoverage, idModelo3DProp]);

  // ── Colocar: un clic crea el mástil (sin modal) ──────────────────

  const handleMastClick = useCallback(async (x, y) => {
    if (!placing || creatingRef.current) return;

    creatingRef.current = true;
    setError(null);

    try {
      const newMast = await mastilesApi.createMastil({
        id_modelo3d: idModelo3D || undefined,
        id_modelo2d: !idModelo3D ? resolvedModelo2DId : undefined,
        id_proyecto: idProyecto,
        posicion_x: x,
        posicion_y: y,
        posicion_z: 0,
        altura: mastHeight,
        tipo: 'Franklin',
      });

      // Nueva referencia: el Modelo3DViewer se actualiza solo (recibe `masts`).
      setMasts((prev) => [...prev, newMast]);
      loadCoverage();
    } catch (err) {
      console.error('[UbicacionMastiles] Error creando mástil:', err);
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'No se pudo guardar el mástil.');
    } finally {
      creatingRef.current = false;
    }
  }, [placing, idModelo3D, resolvedModelo2DId, idProyecto, mastHeight, loadCoverage]);

  const togglePlacing = () => {
    setSelectedMastId(null);
    setPlacing((p) => !p);
  };

  // ── Edición: eliminar / mover / cambiar altura ───────────────────

  const handleDeleteMast = async (id) => {
    try {
      await mastilesApi.deleteMastil(id);
      setMasts((prev) => prev.filter((m) => !sameId(m.id, id)));
      if (sameId(selectedMastId, id)) setSelectedMastId(null);
      loadCoverage();
    } catch (err) {
      console.error('[UbicacionMastiles] Error eliminando mástil:', err);
      setError('No se pudo eliminar el mástil.');
    }
  };

  const handleMoveMast = async (id, x, y) => {
    // Optimista: refleja el movimiento de inmediato en ambos visores.
    setMasts((prev) =>
      prev.map((m) => (sameId(m.id, id) ? { ...m, posicion_x: x, posicion_y: y } : m))
    );

    try {
      const updated = await mastilesApi.updateMastil(id, { posicion_x: x, posicion_y: y });
      setMasts((prev) => prev.map((m) => (sameId(m.id, id) ? { ...m, ...updated } : m)));
      loadCoverage();
    } catch (err) {
      console.error('[UbicacionMastiles] Error moviendo mástil:', err);
      setError('No se pudo guardar la nueva posición del mástil.');
      if (idModelo3D) loadMasts(idModelo3D);
    }
  };

  // La altura se ve al instante; el guardado espera a que el usuario deje de
  // tocar el control (evita una llamada por cada clic en +/−).
  const handleUpdateMastHeight = (id, altura) => {
    setMasts((prev) =>
      prev.map((m) => (sameId(m.id, id) ? { ...m, altura } : m))
    );

    clearTimeout(heightTimers.current[id]);
    heightTimers.current[id] = setTimeout(async () => {
      delete heightTimers.current[id];
      try {
        const updated = await mastilesApi.updateMastil(id, { altura });
        if (!heightTimers.current[id]) {
          setMasts((prev) => prev.map((m) => (sameId(m.id, id) ? { ...m, ...updated } : m)));
        }
        loadCoverage();
      } catch (err) {
        console.error('[UbicacionMastiles] Error actualizando altura:', err);
        setError('No se pudo actualizar la altura del mástil.');
        if (idModelo3D) loadMasts(idModelo3D);
      }
    }, 350);
  };

  const handleSelectMast = (mast) => {
    setSelectedMastId(mast ? mast.id : null);
  };

  const handleConfirmarUbicacion = async () => {
    if (!idProyecto) return onNext?.();
    setConfirming(true);
    setError(null);
    try {
      const data = await mastilesApi.guardarCobertura(idProyecto);
      setCoverageData(data);
      onNext?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : 'No se pudo guardar el resultado de cobertura.');
    } finally {
      setConfirming(false);
    }
  };

  // Esc: termina la colocación y deselecciona
  useEffect(() => {
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      setPlacing(false);
      setSelectedMastId(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // ── Derivados ────────────────────────────────────────────────────

  const selectedIdx = masts.findIndex((m) => sameId(m.id, selectedMastId));
  const selectedMast = selectedIdx >= 0 ? masts[selectedIdx] : null;

  const heightValue = selectedMast ? Number(selectedMast.altura) || mastHeight : mastHeight;

  const handleHeightChange = (h) => {
    if (selectedMast) handleUpdateMastHeight(selectedMast.id, h);
    else setMastHeight(h);
  };

  const isSplit = viewMode === 'split' && idModelo3D && resolvedModelo2DId;

  // ── Render ───────────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3 text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-brand-blue" />
        <span className="text-sm">Cargando datos del proyecto...</span>
      </div>
    );
  }

  return (
    <div className="w-full space-y-3">

      {/* ── Título + indicación en una sola línea ── */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
          Ubicación de Mástiles Captores
        </h1>
        <p className="flex items-center gap-1.5 text-xs text-brand-blue">
          <Info className="w-4 h-4 shrink-0" />
          Elija la altura, pulse «Colocar mástil» y haga clic en el visor 2D.
          Arrastre un mástil para moverlo o selecciónelo para cambiar su altura.
        </p>
      </div>

      {/* ── Error global ── */}
      {error && (
        <div
          role="alert"
          className="p-2.5 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-center gap-2 text-xs"
        >
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            className="p-1 rounded text-red-400 hover:text-red-600 hover:bg-red-100"
            aria-label="Cerrar mensaje"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Resumen (incluye selector de vista y actualizar cobertura) ── */}
      <ResumenUbicacion
        radio={coverageData?.radio_esfera_rodante_r ?? 30}
        totalMastiles={masts.length}
        porcentajeCobertura={coverageData?.porcentaje_cobertura ?? null}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        onRefresh={loadCoverage}
        refreshing={coverageLoading}
      />

      {/* ── Barra de mástil: colocar + altura (queda fija al hacer scroll) ── */}
      <div className="sticky top-0 z-30 bg-white border border-gray-200 rounded-md shadow-sm px-3 py-2 flex flex-wrap items-center gap-x-4 gap-y-2">
        <button
          type="button"
          onClick={togglePlacing}
          disabled={!resolvedModelo2DId}
          className={`flex items-center gap-1.5 px-4 py-1.5 rounded font-bold text-xs transition disabled:opacity-50 ${placing
            ? 'bg-amber-500 hover:bg-amber-600 text-white'
            : 'bg-brand-blue hover:bg-brand-hover text-white'
            }`}
        >
          <MapPin className="w-3.5 h-3.5" />
          {placing ? 'Terminar (Esc)' : 'Colocar mástil'}
        </button>

        {/* A quién afecta la altura */}
        <div className="flex items-center gap-2 text-[11px] text-gray-500 min-w-0">
          {selectedMast ? (
            <>
              <span
                className="w-5 h-5 rounded-full shrink-0 flex items-center justify-center text-[9px] font-bold text-white"
                style={{ backgroundColor: getMastColor(selectedMast.altura) }}
              >
                {selectedIdx + 1}
              </span>
              <span className="font-semibold text-gray-700">Mástil {selectedIdx + 1}</span>
              <span className="hidden md:inline tabular-nums">
                ({fmtNum(selectedMast.posicion_x, 2)}, {fmtNum(selectedMast.posicion_y, 2)})
              </span>
            </>
          ) : (
            <span>{placing ? 'Altura de los mástiles nuevos' : 'Altura del próximo mástil'}</span>
          )}
        </div>

        <HeightControl value={heightValue} onChange={handleHeightChange} />

        {selectedMast && (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => handleDeleteMast(selectedMast.id)}
              className="flex items-center gap-1 px-2.5 py-1.5 rounded border border-red-200 text-red-600 hover:bg-red-50 text-[11px] font-semibold transition"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Eliminar
            </button>
            <button
              type="button"
              onClick={() => setSelectedMastId(null)}
              className="p-1.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100"
              title="Deseleccionar (Esc)"
              aria-label="Deseleccionar mástil"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={() => setShowRecs((v) => !v)}
          aria-expanded={showRecs}
          className="ml-auto flex items-center gap-1 text-[11px] font-semibold text-gray-500 hover:text-brand-blue"
        >
          <Lightbulb className="w-3.5 h-3.5" />
          Recomendaciones
          {showRecs ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
        </button>
      </div>

      {showRecs && (
        <RecomendacionesMastiles
          radio={coverageData?.radio_esfera_rodante_r ?? 30}
          altura={heightValue}
        />
      )}

      {/* ── Visores: ocupan todo el ancho disponible ── */}
      <div
        className={
          isSplit
            ? 'grid grid-cols-1 lg:grid-cols-2 gap-3 min-w-0 items-start'
            : 'flex flex-col gap-3 min-w-0'
        }
      >
        {(viewMode === 'split' || viewMode === '2d') && (
          <div className="bg-white border border-gray-200 rounded-md shadow-sm p-2 min-w-0">
            <span className="block mb-1 text-[11px] font-bold text-gray-600 uppercase">
              Vista 2D — Geometría validada
            </span>

            {resolvedModelo2DId ? (
              <GeometriaViewerMastiles
                idModelo2D={resolvedModelo2DId}
                masts={masts}
                onMastClick={handleMastClick}
                onMastMove={handleMoveMast}
                onSelectMast={handleSelectMast}
                selectedMastId={selectedMastId}
                placing={placing}
                radioEsfera={coverageData?.radio_esfera_rodante_r ?? 30}
                alturaNuevoMastil={mastHeight}
              />
            ) : (
              <div className="py-10 text-center text-gray-400 text-xs">
                No se pudo determinar el Modelo 2D.
              </div>
            )}
          </div>
        )}

        {(viewMode === 'split' || viewMode === '3d') && idModelo3D && (
          <div className={`${isSplit ? 'h-full' : 'h-[75vh]'} min-h-[520px] min-w-0`}>
            <Modelo3DViewer
              idModelo3D={idModelo3D}
              idModelo2D={resolvedModelo2DId}
              masts={masts}
              coverageData={coverageData}
            />
          </div>
        )}
      </div>

      {/* ── Debajo de los visores: datos, sin repetir lo del resumen ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 items-start">
        <PanelMastiles
          masts={masts}
          selectedMastId={selectedMastId}
          onSelect={handleSelectMast}
          onDelete={handleDeleteMast}
        />
        <PanelTernas coverageData={coverageData} masts={masts} onSelect={handleSelectMast} />
        <PanelCubiertas coverageData={coverageData} />
      </div>

      <button
        type="button"
        onClick={handleConfirmarUbicacion}
        disabled={confirming}
        className="w-full py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded text-xs transition flex items-center justify-center gap-2 disabled:opacity-60"
      >
        {confirming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Box className="w-4 h-4" />}
        Confirmar Ubicación → Continuar
      </button>
    </div>
  );
};

export default UbicacionMastiles;