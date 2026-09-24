/**
 * GeometriaViewerMastiles
 *
 * Componente especializado para la página UbicacionMastiles (HU05).
 * Visualiza la geometría 2D validada (read-only, no se puede editar el
 * plano desde acá) y captura clics sobre el canvas para colocar mástiles
 * captores, además de permitir arrastrarlos para moverlos y seleccionarlos
 * para cambiar su altura o eliminarlos desde el panel lateral.
 *
 * IMPORTANTE:
 *  - No modifica GeometriaViewer ni su lógica de edición.
 *  - Usa EXACTAMENTE la misma transformación de coordenadas
 *    (transformPoint / inverseTransformPoint) que GeometriaViewer, para que
 *    un mástil colocado acá caiga en el mismo punto real del edificio que
 *    ve el editor 2D y que usa el generador de Modelo 3D. (La versión
 *    anterior de este archivo tenía los dos ejes invertidos y mostraba
 *    la geometría rotada 180° respecto al resto del sistema.)
 *  - Trae el plano de fondo (líneas reconocidas del PDF/DXF) pidiendo
 *    `getModelo2DEdicion(idModelo2D, { incluirLineas: true })`: el
 *    endpoint de edición normalmente NO trae las líneas (son pesadas y el
 *    editor las pide en cada operación), así que hay que pedirlas
 *    explícitamente acá. Ver la nota al pie de este archivo sobre el
 *    cambio que esto requiere en planos.py / planos.js.
 *  - Los mástiles se persisten en el backend a través de UbicacionMastiles;
 *    este componente solo dibuja los marcadores y notifica al padre
 *    (colocar, mover, seleccionar). Eliminar y cambiar altura se piden
 *    desde MastilPositioner, pero mover (arrastrar) se resuelve acá mismo.
 *
 * Props:
 *   idModelo2D     {string}   UUID del Modelo 2D validado.
 *   masts          {Array}    Mástiles ya persistidos:
 *                             { id, posicion_x, posicion_y, altura, tipo }
 *   onMastClick    {Function} (x, y) → clic en modo colocación (placing=true).
 *   onMastMove     {Function} (id, x, y) → se soltó un mástil arrastrado.
 *   onSelectMast   {Function} (mast|null) → clic sobre un mástil ya
 *                             colocado (fuera de modo colocación); pasa
 *                             null cuando se hace clic en el vacío.
 *   selectedMastId {string}   id del mástil actualmente seleccionado
 *                             (resalta su marcador).
 *   placing        {boolean}  true mientras se espera un clic para colocar.
 *   className      {string}   Clases CSS opcionales para el contenedor.
 */
import React, {useCallback, useEffect, useRef, useState,
} from 'react';

import {
  Stage, Layer, Line, Circle, Rect, Text, Group,
} from 'react-konva';

import {
  Loader2, MapPin, ZoomIn, ZoomOut, RefreshCw, AlertTriangle,
} from 'lucide-react';

import { planosApi } from '../../api/planos';
import { getMastColor } from '../../api/utilsMastilVisual';


// ============================================================
// CONSTANTES
// ============================================================

const COLORS = {
  poly: '#1a6dba',
  levelLinked: '#1a6dba',
  levelFree: '#d97706',
  mastSelected: '#d946ef',
};


// ============================================================
// HELPERS (idénticos a los de GeometriaViewer para consistencia)
// ============================================================

const getPointCoords = (pt) => {
  if (Array.isArray(pt)) return [Number(pt[0]), Number(pt[1])];
  if (pt && typeof pt === 'object') return [Number(pt.x ?? 0), Number(pt.y ?? 0)];
  return [0, 0];
};

const normalizePoints = (points) =>
  (points || []).map((p) => {
    const [x, y] = getPointCoords(p);
    return { x, y };
  });

const getLinePoints = (line) => {
  if (
    line?.x1 !== undefined &&
    line?.y1 !== undefined &&
    line?.x2 !== undefined &&
    line?.y2 !== undefined
  ) {
    return [Number(line.x1), Number(line.y1), Number(line.x2), Number(line.y2)];
  }
  if (Array.isArray(line?.inicio) && Array.isArray(line?.fin)) {
    return [
      Number(line.inicio[0]),
      Number(line.inicio[1]),
      Number(line.fin[0]),
      Number(line.fin[1]),
    ];
  }
  return [0, 0, 0, 0];
};

const getLevelPosition = (level) => {
  if (level?.posicion && typeof level.posicion === 'object' && !Array.isArray(level.posicion)) {
    return [Number(level.posicion.x), Number(level.posicion.y)];
  }
  if (Array.isArray(level?.posicion)) {
    return [Number(level.posicion[0]), Number(level.posicion[1])];
  }
  return [Number(level?.x ?? 0), Number(level?.y ?? 0)];
};

const errorMessage = (err, fallback) => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d?.msg).filter(Boolean).join(' · ') || fallback;
  }
  return err?.message || fallback;
};


// ============================================================
// COMPONENTE
// ============================================================

export const GeometriaViewerMastiles = ({
  idModelo2D,
  masts = [],
  onMastClick = null,
  onMastMove = null,
  onSelectMast = null,
  selectedMastId = null,
  placing = false,
  className = '',
}) => {

  // ── Datos de la geometría ────────────────────────────────
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [poligonos, setPoligonos] = useState([]);
  const [lineas, setLineas] = useState([]);
  const [cotasAltura, setCotasAltura] = useState([]);
  const [boundingBox, setBoundingBox] = useState(null);

  // ── Vista ────────────────────────────────────────────────
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [stageDimensions, setStageDimensions] = useState({ width: 900, height: 480 });

  const containerRef = useRef(null);
  const isDraggingPan = useRef(false);
  const didPanRef = useRef(false);
  const panDistanceRef = useRef(false);
  const draggingMastRef = useRef(false);
  const lastPointerPos = useRef({ x: 0, y: 0 });


  // ── Carga de la geometría validada ───────────────────────

  const loadGeometry = useCallback(async () => {
    if (!idModelo2D) return;

    setLoading(true);
    setError(null);

    try {
      // Se pide con incluirLineas para traer también el plano de fondo
      // (las líneas reconocidas del PDF/DXF): el endpoint de edición no
      // las trae por defecto porque son pesadas y el editor 2D las pide
      // en cada operación de guardado.
      const data = await planosApi.getModelo2DEdicion(idModelo2D, {
        incluirLineas: true,
      });

      if (!data) {
        setError('No se encontró el Modelo 2D.');
        return;
      }

      if (!data.validado) {
        setError(
          'El Modelo 2D aún no está validado. ' +
          'Complete el paso anterior (Validar Geometría) antes de ubicar mástiles.'
        );
        return;
      }

      setPoligonos(data.poligonos || []);
      setLineas(data.lineas || []);
      setCotasAltura(data.cotas_altura || []);
      setBoundingBox(data.bounding_box || null);

    } catch (err) {
      console.error('[GeometriaViewerMastiles] Error cargando Modelo 2D:', err);
      setError(errorMessage(err, 'No se pudo cargar la geometría del Modelo 2D.'));
    } finally {
      setLoading(false);
    }
  }, [idModelo2D]);

  useEffect(() => {
    loadGeometry();
  }, [loadGeometry]);


  // ── Resize ───────────────────────────────────────────────

  useEffect(() => {
    const updateSize = () => {
      if (!containerRef.current) return;
      setStageDimensions({
        width: containerRef.current.clientWidth || 900,
        height: 480,
      });
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);


  // ── Transformación plano ↔ pantalla ─────────────────────
  //
  // EXACTAMENTE la misma fórmula que usa GeometriaViewer.jsx (sin
  // invertir ejes) para que un mástil colocado acá quede en el mismo
  // punto real del edificio en todas las vistas (editor 2D y Modelo 3D).

  const getTransform = () => {
    const margin = 30;
    const cw = stageDimensions.width - margin * 2;
    const ch = stageDimensions.height - margin * 2;

    if (!boundingBox || boundingBox.min_x === undefined) {
      return { scale: zoom, offsetX: margin + pan.x, offsetY: margin + pan.y };
    }

    const bboxWidth = Math.max(boundingBox.max_x - boundingBox.min_x, 1);
    const bboxHeight = Math.max(boundingBox.max_y - boundingBox.min_y, 1);
    const baseScale = Math.min(cw / bboxWidth, ch / bboxHeight);
    const scale = baseScale * zoom;

    const offsetX =
      margin + (cw - bboxWidth * scale) / 2 - boundingBox.min_x * scale + pan.x;
    const offsetY =
      margin + (ch - bboxHeight * scale) / 2 - boundingBox.min_y * scale + pan.y;

    return { scale, offsetX, offsetY };
  };

  const T = getTransform();

  const transformPoint = (x, y) => [
    -y * T.scale + T.offsetX,
    -x * T.scale + T.offsetY,
  ];

  const inverseTransformPoint = (screenX, screenY) => {
    const x = (screenX - T.offsetX) / T.scale;
    const y = (screenY - T.offsetY) / T.scale;
    return [
      -y,
      -x,
    ];
  };

  const pointerToPlan = (stage) => {
    const pos = stage?.getPointerPosition();
    if (!pos) return null;
    return inverseTransformPoint(pos.x, pos.y);
  };


  // ── Zoom y Pan ───────────────────────────────────────────

  const handleWheel = (e) => {
    e.evt.preventDefault();
    const factor = e.evt.deltaY < 0 ? 1.12 : 0.89;
    setZoom((z) => Math.max(0.3, Math.min(20, z * factor)));
  };

  const handlePointerDown = (e) => {
    didPanRef.current = false;
    panDistanceRef.current = 0;

    if (e.target === e.target.getStage()) {
      isDraggingPan.current = true;
      lastPointerPos.current = { x: e.evt.clientX, y: e.evt.clientY };
    }
  };

  const handlePointerMove = (e) => {
    if (!isDraggingPan.current) return;

    const dx = e.evt.clientX - lastPointerPos.current.x;
    const dy = e.evt.clientY - lastPointerPos.current.y;

    lastPointerPos.current = { x: e.evt.clientX, y: e.evt.clientY };
    panDistanceRef.current += Math.abs(dx) + Math.abs(dy);

    if (panDistanceRef.current > 3) {
      didPanRef.current = true;
    }

    setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
  };

  const handlePointerUp = () => {
    isDraggingPan.current = false;
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };


  // ── Handler de clic sobre el fondo (colocar / deseleccionar) ──

  const handleStageClick = (e) => {
    // Ignorar si fue un desplazamiento (pan) o el fin de un arrastre de mástil.
    if (didPanRef.current) {
      didPanRef.current = false;
      return;
    }

    if (draggingMastRef.current) {
      draggingMastRef.current = false;
      return;
    }

    if (placing) {
      if (!onMastClick) return;
      const p = pointerToPlan(e.target.getStage());
      if (p) onMastClick(p[0], p[1]);
      return;
    }

    // Clic en el vacío (no sobre un mástil): limpiar selección.
    if (e.target === e.target.getStage() && onSelectMast) {
      onSelectMast(null);
    }
  };


  // ── Mover un mástil existente (arrastre) ─────────────────

  const handleMastDragEnd = (mast, e) => {
    draggingMastRef.current = true;

    const [x, y] = inverseTransformPoint(e.target.x(), e.target.y());

    if (onMastMove) {
      onMastMove(mast.id, x, y);
    }
  };


  // ── Render ───────────────────────────────────────────────

  if (loading) {
    return (
      <div className={`flex items-center justify-center py-16 ${className}`}>
        <div className="flex flex-col items-center gap-2 text-slate-500">
          <Loader2 className="w-7 h-7 animate-spin text-brand-blue" />
          <span className="text-xs">Cargando geometría del Modelo 2D...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 bg-red-50 border border-red-200 rounded-md flex items-start gap-2 text-xs text-red-700 ${className}`}>
        <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
        <span>{error}</span>
      </div>
    );
  }

  return (
    <div className={`flex flex-col gap-2 ${className}`}>

      {/* ── Mini toolbar: zoom + reset ── */}
      <div className="flex items-center gap-1.5 justify-end">

        {/* Indicador de modo colocación */}
        {placing && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-amber-100 border border-amber-400 rounded-full text-amber-800 text-[11px] font-semibold animate-pulse mr-auto">
            <MapPin className="w-3.5 h-3.5" />
            Haga clic en la geometría para colocar el mástil
          </div>
        )}

        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(20, z * 1.2))}
          className="p-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
          title="Acercar"
        >
          <ZoomIn className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
          className="p-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
          title="Alejar"
        >
          <ZoomOut className="w-3.5 h-3.5" />
        </button>

        <button
          type="button"
          onClick={resetView}
          className="p-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
          title="Restablecer vista"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* ── Canvas ── */}
      <div
        ref={containerRef}
        className={`relative bg-slate-50 border rounded-md overflow-hidden ${
          placing ? 'border-amber-400 ring-2 ring-amber-300' : 'border-gray-300'
        }`}
        style={{ minHeight: 480 }}
      >
        <Stage
          width={stageDimensions.width}
          height={stageDimensions.height}
          onWheel={handleWheel}
          onMouseDown={handlePointerDown}
          onMouseMove={handlePointerMove}
          onMouseUp={handlePointerUp}
          onClick={handleStageClick}
          style={{ cursor: placing ? 'crosshair' : 'grab' }}
        >
          <Layer>

            {/* ── Líneas de fondo: el plano usado para reconocer la geometría ── */}
            {lineas.map((line, idx) => {
              const [x1, y1, x2, y2] = getLinePoints(line);
              const [sx1, sy1] = transformPoint(x1, y1);
              const [sx2, sy2] = transformPoint(x2, y2);
              return (
                <Line
                  key={`line-${idx}`}
                  points={[sx1, sy1, sx2, sy2]}
                  stroke={line.color || '#94a3b8'}
                  strokeWidth={1}
                  dash={[4, 4]}
                  listening={false}
                />
              );
            })}

            {/* ── Polígonos (solo lectura, sin eventos de edición) ── */}
            {poligonos.map((poly) => {
              const points = normalizePoints(poly.puntos);
              const screenPoints = points.flatMap((p) => transformPoint(p.x, p.y));

              return (
                <Group key={poly.id} listening={false}>
                  <Line
                    points={screenPoints}
                    closed
                    fill="#1a6dba22"
                    stroke={COLORS.poly}
                    strokeWidth={2}
                  />
                  {/* Vértices como puntos pequeños */}
                  {points.map((p, vi) => {
                    const [sx, sy] = transformPoint(p.x, p.y);
                    return (
                      <Circle
                        key={`v-${poly.id}-${vi}`}
                        x={sx}
                        y={sy}
                        radius={3}
                        fill={COLORS.poly}
                        stroke="#fff"
                        strokeWidth={1}
                        listening={false}
                      />
                    );
                  })}
                </Group>
              );
            })}

            {/* ── Niveles (cotas de altura, solo informativos) ── */}
            {cotasAltura.map((level, idx) => {
              const [x, y] = getLevelPosition(level);
              const [sx, sy] = transformPoint(x, y);
              const label = level.texto ?? (level.valor != null ? `+${Number(level.valor).toFixed(2)}` : '');
              const w = Math.max(36, String(label).length * 6 + 10);
              const h = 18;
              const linked = level.asociado === true || (level.asociaciones || []).length > 0;

              return (
                <Group key={level.id ?? `cota-${idx}`} x={sx} y={sy} listening={false}>
                  <Rect
                    x={-w / 2} y={-h / 2}
                    width={w} height={h}
                    fill={linked ? COLORS.levelLinked : COLORS.levelFree}
                    stroke="#fff" strokeWidth={1}
                    cornerRadius={3}
                    opacity={0.85}
                  />
                  <Text
                    text={String(label)}
                    x={-w / 2} y={-h / 2}
                    width={w} height={h}
                    align="center" verticalAlign="middle"
                    fontSize={9} fontStyle="bold" fill="#fff"
                  />
                </Group>
              );
            })}

          </Layer>

          {/* ── Capa de marcadores de mástiles (encima de todo) ── */}
          <Layer listening={!placing}>
            {masts.map((mast, idx) => {
              const [sx, sy] = transformPoint(
                Number(mast.posicion_x),
                Number(mast.posicion_y)
              );

              const isSelected = selectedMastId != null
                && String(selectedMastId) === String(mast.id);

              const color = getMastColor(mast.altura);
              const ringColor = isSelected ? COLORS.mastSelected : color;

              return (
                <Group
                  key={mast.id || `mast-${idx}`}
                  x={sx}
                  y={sy}
                  draggable={!placing}
                  onClick={(e) => {
                    e.cancelBubble = true;
                    if (!placing && onSelectMast) onSelectMast(mast);
                  }}
                  onDragEnd={(e) => handleMastDragEnd(mast, e)}
                >
                  {/* Sombra / halo */}
                  <Circle radius={14} fill="#00000018" />
                  {/* Aro de selección */}
                  {isSelected && (
                    <Circle radius={15} stroke={COLORS.mastSelected} strokeWidth={2.5} />
                  )}
                  {/* Pin principal, coloreado según la altura */}
                  <Circle
                    radius={10}
                    fill={color}
                    stroke="#fff"
                    strokeWidth={2.5}
                  />
                  {/* Número de orden */}
                  <Text
                    text={String(idx + 1)}
                    x={-10} y={-8}
                    width={20} height={16}
                    align="center" verticalAlign="middle"
                    fontSize={9} fontStyle="bold" fill="#fff"
                  />
                  {/* Etiqueta de altura debajo del pin */}
                  <Rect
                    x={-16} y={12}
                    width={32} height={13}
                    fill="#fff"
                    stroke={ringColor}
                    strokeWidth={1}
                    cornerRadius={2}
                    opacity={0.9}
                  />
                  <Text
                    text={`${Number(mast.altura).toFixed(1)}m`}
                    x={-16} y={12}
                    width={32} height={13}
                    align="center" verticalAlign="middle"
                    fontSize={8} fontStyle="bold"
                    fill={color}
                  />
                </Group>
              );
            })}
          </Layer>

        </Stage>
      </div>

      {/* ── Leyenda ── */}
      <div className="flex flex-wrap items-center gap-3 text-[10px] text-gray-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#1a6dba]" />
          Superficie
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#1a6dba]" />
          Nivel asociado
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-3 h-3 rounded-sm bg-[#d97706]" />
          Nivel sin asociar
        </span>
        <span className="ml-auto text-[10px] text-gray-400">
          Rueda: zoom · arrastrar fondo: pan · arrastrar mástil: mover
          {placing ? ' · clic: colocar mástil' : ' · clic en mástil: seleccionar'}
        </span>
      </div>

    </div>
  );
};

export default GeometriaViewerMastiles;

// ============================================================
// NOTA — cambios necesarios en planos.py / planos.js
// ============================================================
//
// Este componente pide getModelo2DEdicion(idModelo2D, { incluirLineas: true }).
// El endpoint /modelos2d/{id}/edicion hoy NO devuelve "lineas" a propósito
// (ver planos.py). Hay que agregarle un parámetro opcional que las incluya
// solo cuando se pidan explícitamente, para no pesar las llamadas del
// editor 2D que lo consultan después de cada operación. Ver el mensaje de
// chat para el diff exacto de planos.py y planos.js.