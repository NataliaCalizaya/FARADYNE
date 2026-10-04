import React, {
  useCallback, useEffect, useMemo, useRef, useState,
} from 'react';

import {
  Stage, Layer, Line, Circle, Rect, Text, Group, Shape,
} from 'react-konva';

import {
  Loader2, MapPin, ZoomIn, ZoomOut, RefreshCw, AlertTriangle,
} from 'lucide-react';

import { planosApi } from '../../api/planos';
import { getMastColor } from '../../hooks/utilsMastilVisual';
import {
   GRID_STEPS, DEFAULT_GRID_INDEX,
   fitTransform, snapPoint, gridStride, gridLineValues,
   construirCotas, separacionMaxima,
 } from '../../hooks/utilsGrillaMastiles';
import { CotasTemporales } from './CotasTemporales';

// ============================================================
// CONSTANTES
// ============================================================

const COLORS = {
  poly: '#1a6dba',
  levelLinked: '#1a6dba',
  levelFree: '#d97706',
  mastSelected: '#d946ef',
  gridMinor: '#cbd5e1',
  gridMajor: '#94a3b8',
  snapNode: '#f59e0b',
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
  radioEsfera = 30,
 alturaNuevoMastil = null,
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

  // ── Grilla e imán ────────────────────────────────────────
  const [showGrid, setShowGrid] = useState(true);
  const [snapEnabled, setSnapEnabled] = useState(true);
  const [gridIndex, setGridIndex] = useState(DEFAULT_GRID_INDEX);
  const [hoverNode, setHoverNode] = useState(null); // nodo bajo el cursor al colocar
  const [dragPoint, setDragPoint] = useState(null); // { id, x, y } mientras se arrastra un mástil
  const gridStep = GRID_STEPS[gridIndex];

  // La grilla nace en la esquina mínima del modelo: los nodos quedan alineados
  // con el edificio y es fácil ubicar mástiles en filas y columnas simétricas.
  const gridOrigin = useMemo(
    () => ({ x: boundingBox?.min_x ?? 0, y: boundingBox?.min_y ?? 0 }),
    [boundingBox]
  );

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
  // Mismo mapeo que GeometriaViewer.jsx (pantalla X = y del plano, pantalla
  // Y = x del plano) para que un mástil colocado acá quede en el mismo punto
  // real del edificio en todas las vistas (editor 2D y Modelo 3D).
  //
  // El encuadre (escala y desplazamiento) tiene en cuenta ese intercambio de
  // ejes, así el modelo queda centrado y entero dentro del visor.

  const T = fitTransform(boundingBox, stageDimensions.width, stageDimensions.height, zoom, pan);

  const transformPoint = (x, y) => [
    y * T.scale + T.offsetX,
    x * T.scale + T.offsetY,
  ];

  const inverseTransformPoint = (screenX, screenY) => {
    const x = (screenX - T.offsetX) / T.scale;
    const y = (screenY - T.offsetY) / T.scale;
    return [
      y,
      x,
    ];
  };

  const pointerToPlan = (stage) => {
    const pos = stage?.getPointerPosition();
    if (!pos) return null;
    return inverseTransformPoint(pos.x, pos.y);
  };

  // Punto del plano -> nodo de grilla más cercano (si el imán está activo).
  const snapIfEnabled = (x, y) => (
    snapEnabled ? snapPoint(x, y, gridOrigin, gridStep) : [x, y]
  );


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
    // Al colocar con imán: marcar el nodo al que va a ir el mástil.
   // if (placing && snapEnabled) {
      if (placing) {
        const p = pointerToPlan(e.target.getStage());
        if (p) {
          //const node = snapPoint(p[0], p[1], gridOrigin, gridStep);
          const node = snapIfEnabled(p[0], p[1]);
          setHoverNode((prev) => (
            prev && prev[0] === node[0] && prev[1] === node[1] ? prev : node
          ));
        }
    }

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

  const handlePointerLeave = () => {
    isDraggingPan.current = false;
    setHoverNode(null);
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
      if (p) {
        const [x, y] = snapIfEnabled(p[0], p[1]);
        onMastClick(x, y);
      }
      return;
    }

    // Clic en el vacío (no sobre un mástil): limpiar selección.
    if (e.target === e.target.getStage() && onSelectMast) {
      onSelectMast(null);
    }
  };


  // ── Mover un mástil existente (arrastre) ─────────────────

  // Mientras se arrastra, el mástil salta de nodo en nodo.
  const mastDragBound = (pos) => {
    if (!snapEnabled) return pos;
    const [px, py] = inverseTransformPoint(pos.x, pos.y);
    const [nx, ny] = snapPoint(px, py, gridOrigin, gridStep);
    const [sx, sy] = transformPoint(nx, ny);
    return { x: sx, y: sy };
  };

  const handleMastDragEnd = (mast, e) => {
    draggingMastRef.current = true;
    setDragPoint(null);

    const [rawX, rawY] = inverseTransformPoint(e.target.x(), e.target.y());
    const [x, y] = snapIfEnabled(rawX, rawY);

    if (onMastMove) {
      onMastMove(mast.id, x, y);
    }
  };

  const handleMastDragMove = (mast, e) => {
    const [x, y] = inverseTransformPoint(e.target.x(), e.target.y());
    setDragPoint({ id: mast.id, x, y });
  };

  // ── Grilla (dibujada en un solo trazo por tipo de línea) ─

  const { width: stageW, height: stageH } = stageDimensions;

  let gridX = [];
  let gridY = [];
  if (showGrid) {
    const stride = gridStride(gridStep, T.scale);
    const [xA, yA] = inverseTransformPoint(0, 0);
    const [xB, yB] = inverseTransformPoint(stageW, stageH);
    gridX = gridLineValues(Math.min(xA, xB), Math.max(xA, xB), gridOrigin.x, gridStep, stride);
    gridY = gridLineValues(Math.min(yA, yB), Math.max(yA, yB), gridOrigin.y, gridStep, stride);
  }

  // x constante -> línea horizontal en pantalla; y constante -> vertical.
  const drawGrid = (major) => (ctx, shape) => {
    ctx.beginPath();
    gridX.forEach(({ value, major: isMajor }) => {
      if (isMajor !== major) return;
      const sy = value * T.scale + T.offsetY;
      ctx.moveTo(0, sy);
      ctx.lineTo(stageW, sy);
    });
    gridY.forEach(({ value, major: isMajor }) => {
      if (isMajor !== major) return;
      const sx = value * T.scale + T.offsetX;
      ctx.moveTo(sx, 0);
      ctx.lineTo(sx, stageH);
    });
    ctx.fillStrokeShape(shape);
  };

  // Cotas temporales: al colocar (desde el cursor) o al arrastrar un mástil.
  const origenCotas = placing ? hoverNode : (dragPoint ? [dragPoint.x, dragPoint.y] : null);
  const alturaRef = placing
    ? alturaNuevoMastil
    : masts.find((m) => String(m.id) === String(dragPoint?.id))?.altura;
  const dMaxPar = alturaRef != null
    ? separacionMaxima(radioEsfera, Number(alturaRef)).par
    : null;
  const cotas = origenCotas
    ? construirCotas(origenCotas, masts, { excluirId: dragPoint?.id, dMax: dMaxPar })
    : [];

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

      {/* ── Mini toolbar: grilla + zoom + reset ── */}
      <div className="flex flex-wrap items-center gap-1.5 justify-end">

        {/* Indicador de modo colocación */}
        {placing && (
          <div className="flex items-center gap-1.5 px-3 py-1 bg-amber-100 border border-amber-400 rounded-full text-amber-800 text-[11px] font-semibold animate-pulse mr-auto">
            <MapPin className="w-3.5 h-3.5" />
            Haga clic en la geometría para colocar el mástil
            {snapEnabled && hoverNode && (
              <span className="font-normal tabular-nums">
                {` · x ${hoverNode[0].toFixed(2)} m, y ${hoverNode[1].toFixed(2)} m`}
              </span>
            )}
          </div>
        )}

        {/* Grilla: mostrar, imán y paso */}
        <div className="flex items-center gap-3 px-2.5 py-1 bg-white border border-gray-300 rounded text-[11px] text-gray-600">
          <label className="flex items-center gap-1 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showGrid}
              onChange={(e) => setShowGrid(e.target.checked)}
            />
            Grilla
          </label>

          <label className="flex items-center gap-1 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={snapEnabled}
              onChange={(e) => {
                setSnapEnabled(e.target.checked);
                if (!e.target.checked) setHoverNode(null);
              }}
            />
            Imán
          </label>

          <div className="flex flex-col items-stretch">
            <input
              type="range"
              min={0}
              max={GRID_STEPS.length - 1}
              step={1}
              value={gridIndex}
              onChange={(e) => setGridIndex(Number(e.target.value))}
              className="w-28 accent-sky-500"
              aria-label="Tamaño de la grilla"
              aria-valuetext={`${gridStep} por ${gridStep} metros`}
              title={`Grilla de ${gridStep} m × ${gridStep} m`}
            />
            <div className="flex justify-between text-[9px] text-gray-400 leading-none">
              {GRID_STEPS.map((s) => (
                <span key={s} className={s === gridStep ? 'text-gray-700 font-semibold' : ''}>
                  {s} m
                </span>
              ))}
            </div>
          </div>
        </div>

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
          title="Restablecer vista (centra el modelo)"
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
          onMouseLeave={handlePointerLeave}
          onClick={handleStageClick}
          style={{ cursor: placing ? 'crosshair' : 'grab' }}
        >
          <Layer>

            {/* ── Grilla de ubicación (por debajo de todo) ── */}
            {showGrid && (
              <>
                <Shape
                  listening={false}
                  stroke={COLORS.gridMinor}
                  strokeWidth={0.6}
                  sceneFunc={drawGrid(false)}
                />
                <Shape
                  listening={false}
                  stroke={COLORS.gridMajor}
                  strokeWidth={1}
                  sceneFunc={drawGrid(true)}
                />
              </>
            )}

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
                  dragBoundFunc={mastDragBound}
                  onDragMove={(e) => handleMastDragMove(mast, e)}
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

          {/* ── Nodo de imán bajo el cursor (no captura eventos) ── */}
          <Layer listening={false}>
            {placing && snapEnabled && hoverNode && (() => {
              const [nx, ny] = transformPoint(hoverNode[0], hoverNode[1]);
              return (
                <Group x={nx} y={ny}>
                  <Line points={[-9, 0, 9, 0]} stroke={COLORS.snapNode} strokeWidth={1.5} />
                  <Line points={[0, -9, 0, 9]} stroke={COLORS.snapNode} strokeWidth={1.5} />
                  <Circle radius={6} stroke={COLORS.snapNode} strokeWidth={2} />
                </Group>
              );
            })()}
            {cotas.length > 0 && (
              <CotasTemporales cotas={cotas} transformPoint={transformPoint} />
            )}
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
          {showGrid && ` · grilla ${gridStep} × ${gridStep} m, las líneas más gruesas marcan cada 5 m`}
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