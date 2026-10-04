import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {
  Stage,
  Layer,
  Line,
  Circle,
  Rect,
  Text,
  Group,
} from 'react-konva';

import {
  CheckCircle,
  CheckCircle2,
  AlertTriangle,
  Info,
  Loader2,
  HelpCircle,
  ZoomIn,
  ZoomOut,
  Trash2,
  Ruler,
  Link,
  Unlink,
  Square,
  Triangle,
  Plus,
  Minus,
  X,
  Maximize,
  Minimize,
  MousePointer2,
  Pencil,
  CirclePlus,
  Scan,
  ArrowRight,
} from 'lucide-react';

import { planosApi } from '../../api/planos';
import { modelos3dApi } from '../../api/modelos3d';


// ==========================================================
// CONSTANTES
// ==========================================================

const COLORS = {
  poly: '#1a6dba',
  polySelected: '#d946ef',
  levelLinked: '#1a6dba',
  levelFree: '#d97706',
  levelSelected: '#d946ef',
  sideSelected: '#f59e0b',
  sideLinked: '#16a34a',
  draft: '#2a9d5c',
  measure: '#0f766e',
  measureLeg: '#64748b',
};

const MIN_ZOOM = 0.2;
const MAX_ZOOM = 60;
const FIT_MARGIN = 24;
const MIN_STAGE_HEIGHT = 560;
const DEFAULT_BOX = { min_x: 0, min_y: 0, max_x: 20, max_y: 15 };

// Radio (px de pantalla) dentro del cual la medición se ajusta a un vértice.
const MEASURE_SNAP_PX = 12;

// Tramos más cortos que esto (m) no se dibujan en la medición.
const MIN_MEASURE_LEG = 0.005;


// ==========================================================
// UTILIDADES (funciones puras)
// ==========================================================

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

const getPointCoords = (pt) => {
  if (Array.isArray(pt)) {
    return [Number(pt[0]), Number(pt[1])];
  }

  if (pt && typeof pt === 'object') {
    return [Number(pt.x ?? 0), Number(pt.y ?? 0)];
  }

  return [0, 0];
};

const normalizePoints = (points) =>
  (points || []).map((p) => {
    const [x, y] = getPointCoords(p);
    return { x, y };
  });

// Longitud de un lado (a → b), en metros.
const sideLength = (a, b) => Math.hypot(b.x - a.x, b.y - a.y);

// Área del polígono (fórmula de Gauss / shoelace), en m².
const polygonArea = (pts) => {
  let sum = 0;

  pts.forEach((a, i) => {
    const b = pts[(i + 1) % pts.length];
    sum += a.x * b.y - b.x * a.y;
  });

  return Math.abs(sum) / 2;
};

const formatMeters = (v) => `${v.toFixed(2)} m`;
const formatArea = (v) => `${v.toFixed(2)} m²`;

// Punto de la recta a-b más cercano a (px, py), limitado al segmento.
const closestOnSegment = (px, py, ax, ay, bx, by) => {
  const dx = bx - ax;
  const dy = by - ay;
  const len2 = dx * dx + dy * dy;

  let t = len2 > 0 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0;
  t = Math.max(0, Math.min(1, t));

  const x = ax + t * dx;
  const y = ay + t * dy;

  return { x, y, dist: Math.hypot(px - x, py - y) };
};

// "Lado" = arista i del polígono: va de puntos[i] a puntos[i + 1]
// (el último lado cierra con el primer punto). Igual criterio que el backend.
const nearestSide = (points, px, py) => {
  const pts = normalizePoints(points);
  let best = null;

  pts.forEach((a, i) => {
    const b = pts[(i + 1) % pts.length];
    const c = closestOnSegment(px, py, a.x, a.y, b.x, b.y);

    if (!best || c.dist < best.dist) {
      best = { side: i, ...c };
    }
  });

  return best;
};

const formatLevelText = (value) =>
  `${value >= 0 ? '+' : ''}${value.toFixed(2)}`;

// Acepta "+7.90", "7,9", "-1.2", "−1.20", "±0.00", "7.9 m".
const parseLevelValue = (raw) => {
  const clean = String(raw ?? '')
    .trim()
    .replace(/\s+/g, '')
    .replace(',', '.')
    .replace(/[−–]/g, '-')
    .replace(/^±/, '')
    .replace(/^\+/, '')
    .replace(/m$/i, '');

  if (!/^-?(\d+\.?\d*|\.\d+)$/.test(clean)) {
    return null;
  }

  const value = Number(clean);

  return Number.isFinite(value) ? value : null;
};

const getLevelPosition = (level) => {
  if (
    level?.posicion &&
    typeof level.posicion === 'object' &&
    !Array.isArray(level.posicion)
  ) {
    return [Number(level.posicion.x), Number(level.posicion.y)];
  }

  if (Array.isArray(level?.posicion)) {
    return [Number(level.posicion[0]), Number(level.posicion[1])];
  }

  return [Number(level?.x ?? 0), Number(level?.y ?? 0)];
};

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

const layerName = (capa) =>
  typeof capa === 'string' ? capa : String(capa?.nombre ?? capa?.name ?? '');

const errorMessage = (err, fallback) => {
  const detail = err?.response?.data?.detail;

  if (typeof detail === 'string') {
    return detail;
  }

  // Errores de validación de FastAPI (422): lista de { msg, ... }
  if (Array.isArray(detail)) {
    return (
      detail
        .map((d) => d?.msg)
        .filter(Boolean)
        .join(' · ') || fallback
    );
  }

  return err?.message || fallback;
};

// Caja que contiene todo el contenido: el plano no se re-escala al arrastrar.
const computeContentBox = (poligonos, niveles, base) => {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  const add = (x, y) => {
    if (!Number.isFinite(x) || !Number.isFinite(y)) return;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  };

  if (base && Number.isFinite(base.min_x) && Number.isFinite(base.max_x)) {
    add(base.min_x, base.min_y);
    add(base.max_x, base.max_y);
  }

  (poligonos || []).forEach((p) =>
    normalizePoints(p.puntos).forEach((pt) => add(pt.x, pt.y))
  );

  (niveles || []).forEach((l) => {
    const [x, y] = getLevelPosition(l);
    add(x, y);
  });

  if (!Number.isFinite(minX)) return null;

  return { min_x: minX, min_y: minY, max_x: maxX, max_y: maxY };
};


// ==========================================================
// PEQUEÑOS COMPONENTES DE INTERFAZ
// ==========================================================

const Kbd = ({ children }) => (
  <kbd className="ml-1.5 px-1 py-px rounded bg-white/20 text-[10px] font-mono">
    {children}
  </kbd>
);

// Botón de la paleta flotante (icono + tooltip con atajo).
const ToolButton = ({ icon: Icon, label, shortcut, active, disabled, onClick }) => (
  <div className="relative group">
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={!!active}
      className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all disabled:opacity-40 disabled:pointer-events-none focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue ${active
          ? 'bg-brand-blue text-white shadow-md scale-105'
          : 'text-gray-600 hover:bg-blue-50 hover:text-brand-blue'
        }`}
    >
      <Icon className="w-[18px] h-[18px]" />
    </button>

    <span className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 whitespace-nowrap rounded-md bg-gray-900 text-white text-[11px] px-2 py-1 opacity-0 group-hover:opacity-100 transition-opacity z-30 flex items-center">
      {label}
      {shortcut && <Kbd>{shortcut}</Kbd>}
    </span>
  </div>
);

// Botón de acción dentro del inspector.
const ActionButton = ({
  icon: Icon,
  children,
  onClick,
  disabled,
  variant = 'default',
  active = false,
  title,
}) => {
  const styles = {
    default: 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50',
    primary: 'bg-brand-blue text-white border-brand-blue hover:bg-brand-hover',
    danger: 'bg-white text-red-600 border-red-200 hover:bg-red-50',
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`px-2.5 py-1.5 rounded-md text-[11px] font-medium border flex items-center justify-center gap-1.5 transition disabled:opacity-40 disabled:pointer-events-none focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue ${active ? styles.primary : styles[variant]
        }`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      {children}
    </button>
  );
};

const IconButton = ({ icon: Icon, label, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    title={label}
    aria-label={label}
    className="w-8 h-8 rounded-md flex items-center justify-center text-gray-600 hover:bg-blue-50 hover:text-brand-blue transition focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue"
  >
    <Icon className="w-4 h-4" />
  </button>
);

const StatChip = ({ children, tone = 'neutral', title }) => {
  const tones = {
    neutral: 'bg-gray-100 text-gray-700',
    good: 'bg-emerald-50 text-emerald-700',
    warn: 'bg-amber-50 text-amber-800',
  };

  return (
    <span
      title={title}
      className={`px-2.5 py-1 rounded-full text-[11px] font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
};

// Etiqueta de las cotas de medición, centrada en (x, y) de pantalla.
const MeasureLabel = ({ x, y, text, color = COLORS.measure, bold = false }) => {
  const w = text.length * 5.6 + 10;

  return (
    <Group x={x} y={y} listening={false}>
      <Rect
        x={-w / 2}
        y={-8}
        width={w}
        height={16}
        fill="#fff"
        stroke={color}
        strokeWidth={1}
        cornerRadius={3}
        opacity={0.95}
      />
      <Text
        text={text}
        x={-w / 2}
        y={-8}
        width={w}
        height={16}
        align="center"
        verticalAlign="middle"
        fontSize={10}
        fontStyle={bold ? 'bold' : 'normal'}
        fill={color}
      />
    </Group>
  );
};


// ==========================================================
// COMPONENTE
// ==========================================================

export const GeometriaViewer = ({
  idPlano,
  idModelo2D,
  onGeometriaConfirmed, // eslint-disable-line no-unused-vars
  onNext,
}) => {

  // ========================================================
  // ESTADO DE DATOS
  // ========================================================

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);

  const [poligonos, setPoligonos] = useState([]);
  const [lineas, setLineas] = useState([]);
  const [capas, setCapas] = useState([]);
  const [cotasAltura, setCotasAltura] = useState([]);

  const [boundingBox, setBoundingBox] = useState(null);
  const [isValidated, setIsValidated] = useState(false);


  // ========================================================
  // VISTA
  // ========================================================

  const [view, setView] = useState({ zoom: 1, pan: { x: 0, y: 0 } });
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPanning, setIsPanning] = useState(false);
  const [hoverPolyId, setHoverPolyId] = useState(null);
  const [hoverTarget, setHoverTarget] = useState(false);

  const [stageDimensions, setStageDimensions] = useState({
    width: 1200,
    height: 500,
  });

  const rootRef = useRef(null);
  const containerRef = useRef(null);
  const isDraggingPan = useRef(false);
  const didPanRef = useRef(false);
  const panDistanceRef = useRef(0);
  const lastPointerPos = useRef({ x: 0, y: 0 });


  // ========================================================
  // SELECCIÓN (por id, no por índice: sobrevive a recargas)
  // ========================================================

  const [selectedPolyId, setSelectedPolyId] = useState(null);
  const [selectedSide, setSelectedSide] = useState(null);
  const [selectedVertex, setSelectedVertex] = useState(null);
  const [selectedLevelId, setSelectedLevelId] = useState(null);


  // ========================================================
  // HERRAMIENTA ACTIVA
  // ========================================================

  /*
    null       → seleccionar / mover
    triangle   → creando triángulo (3 clics)
    rectangle  → creando rectángulo (2 clics)
    level      → colocando un nivel (1 clic)
    vertex     → agregando vértices a la superficie seleccionada
    measure    → midiendo una distancia (2 clics, temporal)
  */
  const [mode, setMode] = useState(null);

  const [draft, setDraft] = useState(null);
  const draftRef = useRef(null);
  const pendingLevelRef = useRef(null);

  // Medición temporal: hasta 2 puntos del plano [x, y] y el punto bajo el cursor.
  // No se guarda en el modelo; se descarta al salir de la herramienta.
  const [measure, setMeasure] = useState({ points: [], hover: null });

  // Diálogo para escribir el valor de un nivel (reemplaza a window.prompt).
  const [levelDialog, setLevelDialog] = useState(null);


  // ========================================================
  // COLA DE OPERACIONES
  // ========================================================

  /*
   * Todas las operaciones que modifican el Modelo 2D se ejecutan de a una,
   * en orden, y después de cada una se vuelve a leer el estado del
   * servidor. Así el visor nunca muestra algo que no quedó guardado
   * (superficies "fantasma") ni pierde una edición hecha mientras otra
   * estaba en curso.
   */
  const queueRef = useRef(Promise.resolve());
  const pendingCountRef = useRef(0);
  const draggingVertexRef = useRef(false);


  // ========================================================
  // DERIVADOS
  // ========================================================

  const polyById = useMemo(
    () => new Map(poligonos.map((p) => [String(p.id), p])),
    [poligonos]
  );

  const selectedPoly = selectedPolyId
    ? polyById.get(String(selectedPolyId)) || null
    : null;

  const selectedLevel = selectedLevelId
    ? cotasAltura.find((l) => String(l.id) === String(selectedLevelId)) || null
    : null;

  const busy = saving || generating;


  // ========================================================
  // CARGA INICIAL
  // ========================================================

  const loadPreview = useCallback(async (planoId) => {
    if (!planoId) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await planosApi.getPlanoPreview(planoId);

      if (!data) {
        return;
      }

      setPoligonos(data.poligonos || []);
      setLineas(data.lineas || []);
      setCapas(data.capas || []);
      setCotasAltura(data.cotas_altura || []);
      setBoundingBox(
        computeContentBox(data.poligonos, data.cotas_altura, data.bounding_box) ||
        data.bounding_box ||
        null
      );
      setView({ zoom: 1, pan: { x: 0, y: 0 } });
      setIsValidated(!!data.validado);

    } catch (err) {
      console.error('Error cargando Modelo 2D:', err);

      setError(
        errorMessage(err, 'No se pudo obtener la geometría del plano.')
      );

    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (idPlano) {
      loadPreview(idPlano);
    }
  }, [idPlano, loadPreview]);


  // ========================================================
  // RELEER EL ESTADO EDITABLE DESDE EL SERVIDOR
  // ========================================================

  const refreshModelo = useCallback(async () => {
    // Mientras se arrastra un vértice no se pisa el estado local.
    if (!idModelo2D || draggingVertexRef.current) {
      return;
    }

    const data = await planosApi.getModelo2DEdicion(idModelo2D);

    setPoligonos(data.poligonos || []);
    setCotasAltura(data.cotas_altura || []);

    if (Array.isArray(data.capas)) {
      setCapas(data.capas);
    }

    setIsValidated(!!data.validado);
  }, [idModelo2D]);


  // ========================================================
  // EJECUTAR UNA OPERACIÓN QUE MODIFICA EL MODELO
  // ========================================================

  const runMutation = useCallback(
    (task, fallbackMessage) => {
      pendingCountRef.current += 1;
      setSaving(true);

      const job = queueRef.current.then(async () => {
        setError(null);
        setInfo(null);

        try {
          const result = await task();

          await refreshModelo();

          return { ok: true, result };

        } catch (err) {
          console.error(fallbackMessage, err);

          setError(errorMessage(err, fallbackMessage));

          // Si falló, se vuelve a mostrar lo que hay realmente guardado.
          try {
            await refreshModelo();
          } catch (refreshErr) {
            console.error('No se pudo releer el Modelo 2D:', refreshErr);
          }

          return { ok: false, error: err };
        }
      });

      queueRef.current = job.finally(() => {
        pendingCountRef.current -= 1;

        if (pendingCountRef.current === 0) {
          setSaving(false);
        }
      });

      return job;
    },
    [refreshModelo]
  );


  // ========================================================
  // SELECCIÓN HUÉRFANA (algo se eliminó o cambió en el servidor)
  // ========================================================

  useEffect(() => {
    if (selectedPolyId && !polyById.has(String(selectedPolyId))) {
      setSelectedPolyId(null);
      setSelectedSide(null);
      setSelectedVertex(null);
    }

    if (
      selectedLevelId &&
      !cotasAltura.some((l) => String(l.id) === String(selectedLevelId))
    ) {
      setSelectedLevelId(null);
    }
  }, [polyById, cotasAltura, selectedPolyId, selectedLevelId]);

  // Los avisos informativos se cierran solos.
  useEffect(() => {
    if (!info) return undefined;

    const t = setTimeout(() => setInfo(null), 7000);

    return () => clearTimeout(t);
  }, [info]);


  // ========================================================
  // TRANSFORMACIÓN PLANO ↔ PANTALLA
  // ========================================================

  const computeTransform = (zoomValue, panValue) => {
    const cw = Math.max(stageDimensions.width - FIT_MARGIN * 2, 10);
    const ch = Math.max(stageDimensions.height - FIT_MARGIN * 2, 10);

    const box =
      boundingBox && Number.isFinite(boundingBox.min_x) ? boundingBox : DEFAULT_BOX;

    const spanX = Math.max(box.max_x - box.min_x, 0.5);
    const spanY = Math.max(box.max_y - box.min_y, 0.5);

    // El visor intercambia ejes: pantalla-x depende de y, pantalla-y de x.
    const baseScale = Math.min(cw / spanY, ch / spanX);
    const scale = baseScale * zoomValue;

    const offsetX =
      FIT_MARGIN + (cw - spanY * scale) / 2 - box.min_y * scale + panValue.x;

    const offsetY =
      FIT_MARGIN + (ch - spanX * scale) / 2 - box.min_x * scale + panValue.y;

    return { scale, offsetX, offsetY };
  };

  const T = computeTransform(view.zoom, view.pan);

  const zoomAt = (pointer, factor) => {
    setView((prev) => {
      const newZoom = clamp(prev.zoom * factor, MIN_ZOOM, MAX_ZOOM);
      if (newZoom === prev.zoom) return prev;

      const before = computeTransform(prev.zoom, prev.pan);
      const after = computeTransform(newZoom, prev.pan);

      // punto del plano que está bajo el cursor (ejes intercambiados)
      const planY = (pointer.x - before.offsetX) / before.scale;
      const planX = (pointer.y - before.offsetY) / before.scale;

      return {
        zoom: newZoom,
        pan: {
          x: prev.pan.x + (pointer.x - (planY * after.scale + after.offsetX)),
          y: prev.pan.y + (pointer.y - (planX * after.scale + after.offsetY)),
        },
      };
    });
  };

  // Plano (x, y) → pantalla (y, x)
  const transformPoint = (x, y) => [
    y * T.scale + T.offsetX,
    x * T.scale + T.offsetY,
  ];

  const inverseTransformPoint = (screenX, screenY) => {
    const x = (screenX - T.offsetX) / T.scale;
    const y = (screenY - T.offsetY) / T.scale;

    return [y, x];
  };

  const pointerToPlan = (stage) => {
    const pos = stage?.getPointerPosition();

    if (!pos) {
      return null;
    }

    return inverseTransformPoint(pos.x, pos.y);
  };


  // ========================================================
  // MEDICIÓN TEMPORAL
  // ========================================================

  // Imán a los vértices de las superficies (MEASURE_SNAP_PX en pantalla).
  const snapMeasurePoint = (x, y) => {
    const maxDist = MEASURE_SNAP_PX / T.scale;
    let best = null;

    poligonos.forEach((p) =>
      normalizePoints(p.puntos).forEach((pt) => {
        const d = Math.hypot(pt.x - x, pt.y - y);

        if (d <= maxDist && (!best || d < best.d)) {
          best = { x: pt.x, y: pt.y, d };
        }
      })
    );

    return best ? [best.x, best.y] : [x, y];
  };

  const addMeasurePoint = (x, y) => {
    const point = snapMeasurePoint(x, y);

    setMeasure((prev) =>
      // Con la medición completa, el siguiente clic empieza otra.
      prev.points.length >= 2
        ? { points: [point], hover: null }
        : { points: [...prev.points, point], hover: null }
    );
  };


  // ========================================================
  // ZOOM Y PAN
  // ========================================================

  const handleWheel = (e) => {
    e.evt.preventDefault();

    const pointer = e.target.getStage()?.getPointerPosition();

    if (!pointer) {
      return;
    }

    zoomAt(pointer, e.evt.deltaY < 0 ? 1.12 : 1 / 1.12);
  };

  const handlePointerDown = (e) => {
    didPanRef.current = false;
    panDistanceRef.current = 0;

    // Con una herramienta activa los clics son de la herramienta.
    if (mode) {
      return;
    }

    if (e.target === e.target.getStage()) {
      isDraggingPan.current = true;
      setIsPanning(true);

      lastPointerPos.current = {
        x: e.evt.clientX,
        y: e.evt.clientY,
      };
    }
  };

  const handlePointerMove = (e) => {
    // Medición "elástica": el segundo punto sigue al cursor.
    if (mode === 'measure') {
      const p = pointerToPlan(e.target.getStage());

      if (p) {
        setMeasure((prev) =>
          prev.points.length === 1
            ? { ...prev, hover: snapMeasurePoint(p[0], p[1]) }
            : prev
        );
      }
    }

    if (!isDraggingPan.current) {
      return;
    }

    const dx = e.evt.clientX - lastPointerPos.current.x;
    const dy = e.evt.clientY - lastPointerPos.current.y;

    lastPointerPos.current = {
      x: e.evt.clientX,
      y: e.evt.clientY,
    };

    panDistanceRef.current += Math.abs(dx) + Math.abs(dy);

    if (panDistanceRef.current > 3) {
      didPanRef.current = true;
    }

    setView((prev) => ({
      ...prev,
      pan: { x: prev.pan.x + dx, y: prev.pan.y + dy },
    }));
  };

  const handlePointerUp = () => {
    isDraggingPan.current = false;
    setIsPanning(false);
  };

  const resetView = () => {
    const box = computeContentBox(poligonos, cotasAltura, boundingBox);

    if (box) {
      setBoundingBox(box);
    }

    setView({ zoom: 1, pan: { x: 0, y: 0 } });
  };

  const zoomFromCenter = (factor) =>
    zoomAt(
      { x: stageDimensions.width / 2, y: stageDimensions.height / 2 },
      factor
    );


  // ========================================================
  // HERRAMIENTAS
  // ========================================================

  const clearSelection = () => {
    setSelectedPolyId(null);
    setSelectedSide(null);
    setSelectedVertex(null);
    setSelectedLevelId(null);
  };

  const cancelMode = () => {
    setMode(null);

    draftRef.current = null;
    setDraft(null);

    pendingLevelRef.current = null;

    setMeasure({ points: [], hover: null });
  };

  const toggleMeasureTool = () => {
    if (mode === 'measure') {
      cancelMode();
      return;
    }

    cancelMode();
    clearSelection();

    setError(null);
    setInfo(null);

    setMode('measure');
  };

  const getSurfaceLayer = () => {
    const names = capas.map(layerName).filter(Boolean);

    if (!names.length) {
      return null;
    }

    // Se prefiere la capa de techo (ROOF), no la auxiliar (AUX_ROOF).
    return (
      names.find((n) => n.toUpperCase() === 'ROOF') ||
      names.find((n) => /ROOF/i.test(n) && !/AUX/i.test(n)) ||
      names[0]
    );
  };


  // ========================================================
  // CREAR SUPERFICIES (triángulo / rectángulo)
  // ========================================================

  const startSurface = (kind) => {
    if (!idModelo2D) {
      setError('No existe un Modelo 2D válido.');
      return;
    }

    if (!capas.length) {
      setError(
        'El Modelo 2D no posee capas reconocidas. No se puede crear la superficie.'
      );
      return;
    }

    setError(null);
    setInfo(null);

    clearSelection();
    setMeasure({ points: [], hover: null });

    draftRef.current = { kind, points: [] };
    setDraft({ kind, points: [] });

    setMode(kind);
  };

  const toggleSurfaceTool = (kind) => {
    if (mode === kind) {
      cancelMode();
    } else {
      startSurface(kind);
    }
  };

  const submitSurface = async (kind, points) => {
    const capa = getSurfaceLayer();

    if (!capa) {
      setError('No existe una capa válida para la nueva superficie.');
      cancelMode();
      return;
    }

    const { ok, result } = await runMutation(
      () =>
        kind === 'triangle'
          ? planosApi.createTriangulo(idModelo2D, {
            puntos: points,
            capa,
            page: 0,
            tipo_cubierta: 'pendiente_por_resolver',
          })
          : planosApi.createRectangulo(idModelo2D, {
            x1: points[0][0],
            y1: points[0][1],
            x2: points[1][0],
            y2: points[1][1],
            capa,
            page: 0,
            tipo_cubierta: 'pendiente_por_resolver',
          }),
      kind === 'triangle'
        ? 'No se pudo crear el triángulo.'
        : 'No se pudo crear el rectángulo.'
    );

    draftRef.current = null;
    setDraft(null);

    if (ok && result?.poligono?.id) {
      setSelectedPolyId(result.poligono.id);
      setSelectedSide(null);
    }
  };

  /*
   * IMPORTANTE: los puntos se acumulan en una ref y la creación se dispara
   * desde el manejador del clic, NO desde dentro de un setState. React
   * puede ejecutar dos veces las funciones de setState (StrictMode); si
   * ahí se llamaba a la API, cada triángulo se creaba dos veces.
   */
  const addSurfacePoint = (x, y) => {
    const current = draftRef.current;

    // Ya se completó y se está guardando: cualquier clic extra se ignora.
    if (!current || current.submitted) {
      return;
    }

    const points = [...current.points, [x, y]];
    const needed = current.kind === 'triangle' ? 3 : 2;

    if (points.length < needed) {
      draftRef.current = { ...current, points };
      setDraft({ ...current, points });
      return;
    }

    // Superficie completa: se deja de capturar clics y se crea UNA vez.
    draftRef.current = { ...current, points, submitted: true };
    setDraft({ ...current, points });
    setMode(null);

    submitSurface(current.kind, points);
  };


  // ========================================================
  // NIVELES: CREAR / MODIFICAR / ELIMINAR
  // ========================================================

  const openCreateLevel = () => {
    if (!idModelo2D) {
      return;
    }

    cancelMode();
    setLevelDialog({ kind: 'create', value: '', error: '' });
  };

  const openEditLevel = (level) => {
    if (!level?.id || !idModelo2D) {
      return;
    }

    setLevelDialog({
      kind: 'edit',
      level,
      value: String(level.valor),
      error: '',
    });
  };

  const confirmLevelDialog = async () => {
    const d = levelDialog;

    if (!d) {
      return;
    }

    const valor = parseLevelValue(d.value);

    if (valor === null) {
      setLevelDialog({
        ...d,
        error: 'Ingrese un número válido, por ejemplo +7.90 o -1,20.',
      });
      return;
    }

    setLevelDialog(null);

    if (d.kind === 'create') {
      // Ahora hay que hacer clic en el plano para ubicarlo.
      setError(null);
      setInfo(null);
      pendingLevelRef.current = { valor };
      setMode('level');
      return;
    }

    await runMutation(
      () =>
        planosApi.updateNivel(idModelo2D, d.level.id, {
          valor,
          texto: formatLevelText(valor),
        }),
      'No se pudo actualizar el nivel.'
    );
  };

  const placeLevel = async (x, y) => {
    const pending = pendingLevelRef.current;

    if (!pending) {
      return;
    }

    pendingLevelRef.current = null;
    setMode(null);

    const { ok, result } = await runMutation(
      () =>
        planosApi.createNivel(idModelo2D, {
          valor: pending.valor,
          texto: formatLevelText(pending.valor),
          punto_seleccionado: { x, y },
          page: 0,
          // Si hay una superficie cerca, se asocia sola a su lado más cercano.
          asociar_automaticamente: true,
        }),
      'No se pudo crear el nivel.'
    );

    if (!ok) {
      return;
    }

    const nivel = result?.nivel;

    if (nivel?.id) {
      setSelectedLevelId(nivel.id);
    }

    if (nivel && nivel.asociado === false) {
      setInfo(
        'Nivel creado sin asociar (no hay una superficie cerca). ' +
        'Seleccione una superficie, elija su lado y presione «Asociar».'
      );
    }
  };

  const handleDeleteLevel = async () => {
    if (!selectedLevel?.id || !idModelo2D) {
      return;
    }

    const { ok } = await runMutation(
      () => planosApi.deleteNivel(idModelo2D, selectedLevel.id),
      'No se pudo eliminar el nivel.'
    );

    if (ok) {
      setSelectedLevelId(null);
    }
  };


  // ========================================================
  // ASOCIAR / DESASOCIAR NIVEL ↔ LADO DE SUPERFICIE
  // ========================================================

  const levelIsLinkedTo = (level, polyId) =>
    (level?.asociaciones || []).some(
      (a) => String(a.id_poligono) === String(polyId)
    );

  const handleAssociateLevel = async () => {
    if (!selectedPoly || !selectedLevel || !idModelo2D) {
      setError('Seleccione primero una superficie y un nivel.');
      return;
    }

    const sides = (selectedPoly.puntos || []).length;

    // Sin lado elegido el backend usa el lado más cercano al nivel.
    const lado =
      selectedSide !== null && selectedSide < sides ? selectedSide : undefined;

    const { ok } = await runMutation(
      () =>
        planosApi.associateNivel(
          idModelo2D,
          selectedPoly.id,
          selectedLevel.id,
          lado
        ),
      'No se pudo asociar el nivel.'
    );

    if (ok) {
      setInfo(
        lado !== undefined
          ? `Nivel ${selectedLevel.texto ?? selectedLevel.valor} asociado al lado ${lado}.`
          : `Nivel ${selectedLevel.texto ?? selectedLevel.valor} asociado al lado más cercano.`
      );
    }
  };

  const handleDisassociateLevel = async () => {
    if (!selectedLevel || !idModelo2D) {
      setError('Seleccione el nivel que desea desasociar.');
      return;
    }

    const links = selectedLevel.asociaciones || [];

    // Si no hay superficie elegida y el nivel tiene una sola, se usa esa.
    const polyId =
      selectedPoly?.id ?? (links.length === 1 ? links[0].id_poligono : null);

    if (!polyId) {
      setError(
        'Seleccione la superficie de la que desea desasociar el nivel.'
      );
      return;
    }

    if (!levelIsLinkedTo(selectedLevel, polyId)) {
      setError('El nivel no está asociado a esa superficie.');
      return;
    }

    const { ok } = await runMutation(
      () => planosApi.disassociateNivel(idModelo2D, polyId, selectedLevel.id),
      'No se pudo desasociar el nivel.'
    );

    if (ok) {
      setInfo(
        `Nivel ${selectedLevel.texto ?? selectedLevel.valor} desasociado. ` +
        'El nivel se conserva y puede asociarse de nuevo.'
      );
    }
  };


  // ========================================================
  // POLÍGONOS: MOVER / AGREGAR / ELIMINAR VÉRTICES Y ELIMINAR
  // ========================================================

  const handleVertexDrag = (polyId, vertexIndex, screenX, screenY) => {
    const [x, y] = inverseTransformPoint(screenX, screenY);

    setPoligonos((prev) =>
      prev.map((p) => {
        if (String(p.id) !== String(polyId)) {
          return p;
        }

        const puntos = normalizePoints(p.puntos);
        puntos[vertexIndex] = { x, y };

        return { ...p, puntos };
      })
    );
  };

  const handleVertexDragEnd = async (poly, vertexIndex, screenX, screenY) => {
    draggingVertexRef.current = false;

    const [x, y] = inverseTransformPoint(screenX, screenY);

    const puntos = normalizePoints(poly.puntos);
    puntos[vertexIndex] = { x, y };

    await runMutation(
      () => planosApi.updatePoligono(idModelo2D, poly.id, { puntos }),
      'No se pudo mover el vértice.'
    );
  };

  const handleAddVertex = async (poly, x, y) => {
    if (!poly?.id || !idModelo2D) {
      return;
    }

    // El backend lo inserta sobre el lado más cercano al punto.
    const { ok } = await runMutation(
      () => planosApi.addVertice(idModelo2D, poly.id, { punto: { x, y } }),
      'No se pudo agregar el vértice.'
    );

    if (ok) {
      setSelectedSide(null);
      setSelectedVertex(null);
    }
  };

  const handleRemoveVertex = async (poly, vertexIndex) => {
    if (!poly?.id || !idModelo2D) {
      return;
    }

    if ((poly.puntos || []).length <= 3) {
      setError('Un polígono debe conservar al menos 3 vértices.');
      return;
    }

    const { ok } = await runMutation(
      () => planosApi.removeVertice(idModelo2D, poly.id, vertexIndex),
      'No se pudo eliminar el vértice.'
    );

    if (ok) {
      setSelectedVertex(null);
      setSelectedSide(null);
    }
  };

  const handleDeletePolygon = async () => {
    if (!selectedPoly?.id || !idModelo2D) {
      return;
    }

    const { ok } = await runMutation(
      () => planosApi.deletePoligono(idModelo2D, selectedPoly.id),
      'No se pudo eliminar la superficie.'
    );

    if (ok) {
      setSelectedPolyId(null);
      setSelectedSide(null);
      setSelectedVertex(null);
    }
  };

  const toggleVertexMode = () => {
    if (mode === 'vertex') {
      cancelMode();
      return;
    }

    if (!selectedPoly) {
      setError('Seleccione primero la superficie a la que desea agregar vértices.');
      return;
    }

    setError(null);
    setInfo(null);
    setMode('vertex');
  };


  // ========================================================
  // EVENTOS DEL STAGE
  // ========================================================

  const handleStageClick = (e) => {
    // El clic que termina un desplazamiento (pan) no es una selección.
    if (didPanRef.current) {
      didPanRef.current = false;
      return;
    }

    const stage = e.target.getStage();

    if (mode === 'triangle' || mode === 'rectangle') {
      const p = pointerToPlan(stage);

      if (p) {
        addSurfacePoint(p[0], p[1]);
      }

      return;
    }

    if (mode === 'level') {
      const p = pointerToPlan(stage);

      if (p) {
        placeLevel(p[0], p[1]);
      }

      return;
    }

    if (mode === 'vertex') {
      const p = pointerToPlan(stage);

      if (p && selectedPoly) {
        handleAddVertex(selectedPoly, p[0], p[1]);
      }

      return;
    }

    if (mode === 'measure') {
      const p = pointerToPlan(stage);

      if (p) {
        addMeasurePoint(p[0], p[1]);
      }

      return;
    }

    if (e.target === stage) {
      clearSelection();
    }
  };

  const handlePolygonClick = (e, poly) => {
    e.cancelBubble = true;

    const p = pointerToPlan(e.target.getStage());

    setSelectedPolyId(poly.id);
    setSelectedVertex(null);

    // El lado más cercano al clic queda marcado para asociarle un nivel.
    if (p) {
      const near = nearestSide(poly.points ?? poly.puntos, p[0], p[1]);
      setSelectedSide(near ? near.side : null);
    }
  };

  // Cursor "pointer" al pasar sobre algo que se puede seleccionar.
  const hoverOn = (polyId = null) => {
    if (mode) return;
    setHoverTarget(true);
    setHoverPolyId(polyId);
  };

  const hoverOff = () => {
    setHoverTarget(false);
    setHoverPolyId(null);
  };


  // ========================================================
  // CONFIRMAR / GENERAR 3D
  // ========================================================

  const handleConfirmGeometry = async () => {
    if (!idModelo2D) {
      return;
    }

    const { ok, result } = await runMutation(
      () => planosApi.validarModelo2D(idModelo2D),
      'No se pudo guardar la validación del Modelo 2D.'
    );

    if (!ok) {
      return;
    }

    setIsValidated(true);

    const sinPendiente = result?.poligonos_sin_pendiente?.length ?? 0;

    if (sinPendiente > 0) {
      setInfo(
        `Geometría confirmada. ${sinPendiente} superficie(s) todavía no tienen ` +
        'pendiente definida (necesitan dos niveles asociados a lados distintos).'
      );
    }
  };

  const handleGenerate3D = async () => {
    if (!idModelo2D) {
      return;
    }

    try {
      setGenerating(true);
      setError(null);

      // Upsert: crea o actualiza el Modelo 3D.
      await modelos3dApi.generateModelo3D({ id_modelo2d: idModelo2D });

      if (onNext) {
        onNext();
      }

    } catch (err) {
      console.error('[MODELO 3D] Error generando modelo 3D:', err);

      setError(errorMessage(err, 'No se pudo generar el modelo 3D.'));

    } finally {
      setGenerating(false);
    }
  };


  // ========================================================
  // PANTALLA COMPLETA Y TAMAÑO
  // ========================================================

  useEffect(() => {
    const onChange = () =>
      setIsFullscreen(document.fullscreenElement === rootRef.current);

    document.addEventListener('fullscreenchange', onChange);

    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const toggleFullscreen = () => {
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else {
      rootRef.current?.requestFullscreen?.();
    }
  };

  useEffect(() => {
    const updateSize = () => {
      const el = containerRef.current;

      if (!el) {
        return;
      }

      const width = el.clientWidth || 1200;
      const ratio = isFullscreen ? 0.7 : 0.88;
      const height = Math.max(
        MIN_STAGE_HEIGHT,
        Math.round(window.innerHeight * ratio)
      );

      setStageDimensions((prev) =>
        prev.width === width && prev.height === height ? prev : { width, height }
      );
    };

    updateSize();

    window.addEventListener('resize', updateSize);

    let observer = null;

    if (typeof ResizeObserver !== 'undefined' && containerRef.current) {
      observer = new ResizeObserver(updateSize);
      observer.observe(containerRef.current);
    }

    return () => {
      window.removeEventListener('resize', updateSize);
      if (observer) observer.disconnect();
    };
  }, [isFullscreen]);


  // ========================================================
  // ATAJOS DE TECLADO
  // ========================================================

  /*
   * Los atajos leen siempre la última versión de las acciones a través de
   * una ref, así el listener se registra una sola vez.
   */
  const actionsRef = useRef({});

  actionsRef.current = {
    locked: busy || !!levelDialog,
    select: cancelMode,
    triangle: () => toggleSurfaceTool('triangle'),
    rectangle: () => toggleSurfaceTool('rectangle'),
    level: openCreateLevel,
    measure: toggleMeasureTool,
    fit: resetView,
  };

  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        actionsRef.current.select();
        setLevelDialog(null);
        return;
      }

      if (e.ctrlKey || e.metaKey || e.altKey) {
        return;
      }

      const tag = e.target?.tagName;

      if (tag === 'INPUT' || tag === 'TEXTAREA') {
        return;
      }

      const a = actionsRef.current;

      if (a.locked) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case 'v': a.select(); break;
        case 't': a.triangle(); break;
        case 'r': a.rectangle(); break;
        case 'n': a.level(); break;
        case 'm': a.measure(); break;
        case 'f': a.fit(); break;
        default: break;
      }
    };

    window.addEventListener('keydown', onKeyDown);

    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);


  // ========================================================
  // DATOS DE DIBUJO
  // ========================================================

  const getPreviewPoints = () => {
    if (!draft) {
      return [];
    }

    if (draft.kind === 'rectangle' && draft.points.length === 2) {
      const [[x1, y1], [x2, y2]] = draft.points;

      return [
        [x1, y1],
        [x2, y1],
        [x2, y2],
        [x1, y2],
      ];
    }

    return draft.points;
  };

  const previewPoints = getPreviewPoints();

  // Lados de la superficie seleccionada que tienen niveles asociados.
  const linkedSides = new Map();

  if (selectedPoly) {
    cotasAltura.forEach((level) => {
      (level.asociaciones || []).forEach((a) => {
        if (String(a.id_poligono) === String(selectedPoly.id)) {
          const side = Number(a.lado);
          const texts = linkedSides.get(side) || [];

          texts.push(level.texto ?? String(level.valor));
          linkedSides.set(side, texts);
        }
      });
    });
  }

  // Medidas de la superficie seleccionada (se recalculan en vivo al
  // arrastrar, agregar o quitar vértices).
  const selectedPts = selectedPoly ? normalizePoints(selectedPoly.puntos) : [];

  const sideLengths = selectedPts.map((a, i) =>
    sideLength(a, selectedPts[(i + 1) % selectedPts.length])
  );

  const selectedArea = polygonArea(selectedPts);
  const selectedPerimeter = sideLengths.reduce((s, v) => s + v, 0);

  // La superficie seleccionada se dibuja al final (queda arriba).
  const orderedPolys = selectedPoly
    ? [
      ...poligonos.filter((p) => String(p.id) !== String(selectedPoly.id)),
      selectedPoly,
    ]
    : poligonos;

  const isEmptyGeometry =
    !loading && poligonos.length === 0 && lineas.length === 0;

  const toolsLocked = busy;

  const roleOf = (poly, levelId) => {
    const id = String(levelId);

    if (poly.nivel_bajo && String(poly.nivel_bajo.id) === id) return 'bajo';
    if (poly.nivel_alto && String(poly.nivel_alto.id) === id) return 'alto';
    if (poly.nivel_medio && String(poly.nivel_medio.id) === id) return 'medio';

    return '—';
  };

  const slopeDefined = !!selectedPoly?.pendiente?.definida;

  const pendienteText = (poly) => {
    const p = poly?.pendiente;

    if (p?.definida) {
      return `Pendiente definida · desnivel ${Number(p.desnivel).toFixed(2)} m`;
    }

    return 'Sin pendiente: faltan dos niveles en lados distintos';
  };

  const withoutSlope = poligonos.filter((p) => !p.pendiente?.definida).length;
  const linkedLevels = cotasAltura.filter(
    (l) => (l.asociaciones || []).length > 0
  ).length;

  const canvasCursor = mode
    ? 'crosshair'
    : isPanning && didPanRef.current
      ? 'grabbing'
      : hoverTarget
        ? 'pointer'
        : 'grab';

  const levelPreview =
    levelDialog && parseLevelValue(levelDialog.value) !== null
      ? formatLevelText(parseLevelValue(levelDialog.value))
      : null;


  // ========================================================
  // RENDER
  // ========================================================

  return (

    <div
      ref={rootRef}
      className={`space-y-3 ${isFullscreen ? 'bg-white p-4 overflow-auto h-screen' : ''}`}
    >

      {/* ====================================================
          BARRA DE ESTADO / AYUDA CONTEXTUAL
      ==================================================== */}

      <div
        className={`rounded-lg border px-3.5 py-2.5 flex flex-wrap items-center gap-3 text-xs transition-colors ${mode
            ? 'bg-blue-50 border-blue-200 text-blue-900'
            : 'bg-white border-gray-200 text-gray-600'
          }`}
      >
        {mode ? (
          <Info className="w-4 h-4 shrink-0 text-brand-blue" />
        ) : (
          <MousePointer2 className="w-4 h-4 shrink-0 text-gray-400" />
        )}

        <div className="flex-1 min-w-[240px]">
          {mode === 'triangle' && (
            <>
              <strong>Triángulo:</strong> haga clic en 3 puntos del plano. Se
              crea automáticamente al marcar el tercero.
            </>
          )}

          {mode === 'rectangle' && (
            <>
              <strong>Rectángulo:</strong> haga clic en una esquina y luego en
              la esquina opuesta.
            </>
          )}

          {mode === 'level' && (
            <>
              <strong>Nivel:</strong> haga clic donde quiere colocarlo. Si hay
              una superficie cerca, se asocia sola a su lado más cercano.
            </>
          )}

          {mode === 'vertex' && (
            <>
              <strong>Agregar vértice:</strong> haga clic sobre un lado de la
              superficie seleccionada. Puede agregar varios.
            </>
          )}

          {mode === 'measure' && (
            <>
              <strong>Medir:</strong> haga clic en el punto de origen y luego en
              el destino. Se ajusta a los vértices cercanos. Un clic más inicia
              otra medición; la medición es temporal y no se guarda.
            </>
          )}

          {!mode && (
            <>
              Seleccione una superficie o un nivel con un clic. Arrastre un
              vértice para moverlo, o use la paleta de la izquierda para
              agregar elementos.
            </>
          )}
        </div>

        {/* Progreso de puntos del triángulo / rectángulo */}
        {(mode === 'triangle' || mode === 'rectangle') && (
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {Array.from({ length: mode === 'triangle' ? 3 : 2 }).map((_, i) => (
              <span
                key={i}
                className={`w-2.5 h-2.5 rounded-full transition-colors ${i < (draft?.points.length ?? 0)
                    ? 'bg-emerald-500'
                    : 'bg-blue-200'
                  }`}
              />
            ))}
          </div>
        )}

        {mode && (
          <button
            type="button"
            onClick={cancelMode}
            className="px-2.5 py-1 rounded-md text-[11px] font-medium bg-white border border-blue-200 text-blue-800 hover:bg-blue-100 flex items-center gap-1 transition"
          >
            {mode === 'vertex' || mode === 'measure' ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5" /> Listo
              </>
            ) : (
              <>
                <X className="w-3.5 h-3.5" /> Cancelar
              </>
            )}
            <Kbd>Esc</Kbd>
          </button>
        )}

        {busy && (
          <span className="text-xs text-gray-500 flex items-center gap-1.5">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            Guardando...
          </span>
        )}
      </div>


      {/* ====================================================
          CANVAS + HERRAMIENTAS FLOTANTES
      ==================================================== */}

      <div
        ref={containerRef}
        className="relative bg-slate-50 border border-gray-300 rounded-xl flex items-center justify-center overflow-hidden"
        style={{
          minHeight: stageDimensions.height,
          backgroundImage:
            'radial-gradient(circle, #cbd5e1 1px, transparent 1px)',
          backgroundSize: '22px 22px',
        }}
      >

        {/* ---------- PALETA DE HERRAMIENTAS ---------- */}

        <div className="absolute left-3 top-3 z-20 flex flex-col gap-1 p-1.5 bg-white/95 backdrop-blur rounded-xl border border-gray-200 shadow-lg">

          <ToolButton
            icon={MousePointer2}
            label="Seleccionar y mover"
            shortcut="V"
            active={!mode}
            onClick={cancelMode}
          />

          <div className="h-px bg-gray-200 mx-1.5 my-0.5" />

          <ToolButton
            icon={Triangle}
            label="Dibujar triángulo"
            shortcut="T"
            active={mode === 'triangle'}
            disabled={busy}
            onClick={() => toggleSurfaceTool('triangle')}
          />

          <ToolButton
            icon={Square}
            label="Dibujar rectángulo"
            shortcut="R"
            active={mode === 'rectangle'}
            disabled={busy}
            onClick={() => toggleSurfaceTool('rectangle')}
          />

          <ToolButton
            icon={CirclePlus}
            label="Agregar nivel"
            shortcut="N"
            active={mode === 'level' || levelDialog?.kind === 'create'}
            disabled={toolsLocked || !idModelo2D}
            onClick={() => (mode === 'level' ? cancelMode() : openCreateLevel())}
          />

          <ToolButton
            icon={Ruler}
            label="Medir distancia"
            shortcut="M"
            active={mode === 'measure'}
            onClick={toggleMeasureTool}
          />

        </div>


        {/* ---------- AVISOS (error / info) ---------- */}

        {(error || info) && (
          <div className="absolute top-3 left-1/2 -translate-x-1/2 z-30 w-full max-w-lg px-16 pointer-events-none">
            <div
              role={error ? 'alert' : 'status'}
              className={`pointer-events-auto animate-fade-in flex items-start gap-2 p-3 rounded-lg border shadow-lg text-xs ${error
                  ? 'bg-red-50 border-red-200 text-red-800'
                  : 'bg-blue-50 border-blue-200 text-blue-900'
                }`}
            >
              {error ? (
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
              ) : (
                <Info className="w-4 h-4 text-brand-blue shrink-0 mt-0.5" />
              )}

              <span className="flex-1">{error || info}</span>

              <button
                type="button"
                onClick={() => (error ? setError(null) : setInfo(null))}
                className="opacity-60 hover:opacity-100 transition"
                aria-label="Cerrar aviso"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}


        {/* ---------- INSPECTOR CONTEXTUAL ---------- */}

        {(selectedPoly || selectedLevel) && (
          <aside className="absolute right-3 top-3 z-20 w-72 max-h-[calc(100%-5.5rem)] overflow-y-auto bg-white/95 backdrop-blur rounded-xl border border-gray-200 shadow-lg divide-y divide-gray-100 text-xs">

            {selectedPoly && (
              <section className="p-3 space-y-3">

                <header className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold text-gray-800 flex items-center gap-1.5">
                      <Square className="w-3.5 h-3.5 text-fuchsia-500" />
                      Superficie
                    </div>
                    <div className="text-[11px] text-gray-500 truncate">
                      {selectedPoly.id}
                      {selectedPoly.tipo ? ` · ${selectedPoly.tipo}` : ''}
                      {' · '}
                      {(selectedPoly.puntos || []).length} vértices
                      {` · ${formatArea(selectedArea)}`}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={clearSelection}
                    className="text-gray-400 hover:text-gray-700 transition"
                    aria-label="Deseleccionar"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </header>

                <div
                  className={`rounded-md px-2.5 py-1.5 text-[11px] flex items-start gap-1.5 ${slopeDefined
                      ? 'bg-emerald-50 text-emerald-800'
                      : 'bg-amber-50 text-amber-800'
                    }`}
                >
                  {slopeDefined ? (
                    <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-px" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
                  )}
                  {pendienteText(selectedPoly)}
                </div>

                {/* Área y perímetro */}
                <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                  <div className="rounded-md bg-gray-50 px-2.5 py-1.5">
                    <div className="text-gray-500">Área</div>
                    <div className="font-semibold text-gray-800 tabular-nums">
                      {formatArea(selectedArea)}
                    </div>
                  </div>

                  <div className="rounded-md bg-gray-50 px-2.5 py-1.5">
                    <div className="text-gray-500">Perímetro</div>
                    <div className="font-semibold text-gray-800 tabular-nums">
                      {formatMeters(selectedPerimeter)}
                    </div>
                  </div>
                </div>

                {/* Lados: longitud + nivel asociado. Clic para elegir el lado. */}
                <div>
                  <div className="text-[11px] text-gray-500 mb-1.5">
                    Lados · clic para elegir
                  </div>

                  <ul className="max-h-40 overflow-y-auto space-y-1 pr-0.5">
                    {selectedPts.map((_, i) => {
                      const chosen = selectedSide === i;
                      const linked = linkedSides.has(i);

                      return (
                        <li key={i}>
                          <button
                            type="button"
                            onClick={() => setSelectedSide(chosen ? null : i)}
                            title={
                              linked
                                ? `Nivel: ${linkedSides.get(i).join(' / ')}`
                                : `Lado ${i}`
                            }
                            className={`w-full flex items-center gap-2 px-2 py-1 rounded-md border text-[11px] transition ${chosen
                                ? 'bg-amber-500 border-amber-500 text-white'
                                : linked
                                  ? 'bg-emerald-50 border-emerald-300 text-emerald-800 hover:bg-emerald-100'
                                  : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                              }`}
                          >
                            <span className="font-semibold w-6 text-left">L{i}</span>
                            <span className="tabular-nums flex-1 text-left">
                              {formatMeters(sideLengths[i])}
                            </span>
                            {linked && (
                              <span
                                className={`font-medium truncate ${chosen ? 'text-white' : 'text-emerald-700'}`}
                              >
                                {linkedSides.get(i).join(' / ')}
                              </span>
                            )}
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>

                {(selectedPoly.niveles || []).length > 0 && (
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-gray-500">
                        <th className="font-medium pr-2 pb-1">Lado</th>
                        <th className="font-medium pr-2 pb-1">Nivel</th>
                        <th className="font-medium pb-1">Rol</th>
                      </tr>
                    </thead>
                    <tbody className="text-gray-700">
                      {(selectedPoly.niveles || []).map((n) => (
                        <tr key={`${n.id}-${n.lado}`}>
                          <td className="pr-2">{n.lado}</td>
                          <td className="pr-2">{n.texto ?? n.valor}</td>
                          <td>{roleOf(selectedPoly, n.id)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}

                <div className="grid grid-cols-2 gap-1.5">
                  <ActionButton
                    icon={Plus}
                    active={mode === 'vertex'}
                    disabled={busy || (!!mode && mode !== 'vertex')}
                    onClick={toggleVertexMode}
                    title="Haga clic sobre un lado de la superficie para insertar un vértice"
                  >
                    Agregar vértice
                  </ActionButton>

                  <ActionButton
                    icon={Minus}
                    disabled={toolsLocked || !!mode || selectedVertex === null}
                    onClick={() => handleRemoveVertex(selectedPoly, selectedVertex)}
                    title="Seleccione un vértice con un clic, o haga doble clic sobre él"
                  >
                    {selectedVertex !== null
                      ? `Quitar vértice ${selectedVertex}`
                      : 'Quitar vértice'}
                  </ActionButton>
                </div>

                <ActionButton
                  icon={Trash2}
                  variant="danger"
                  disabled={toolsLocked || !!mode}
                  onClick={handleDeletePolygon}
                >
                  Eliminar superficie
                </ActionButton>

              </section>
            )}

            {selectedLevel && (
              <section className="p-3 space-y-3">

                <header className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[13px] font-semibold text-gray-800 flex items-center gap-1.5">
                      <CirclePlus className="w-3.5 h-3.5 text-amber-600" />
                      Nivel {selectedLevel.texto ?? selectedLevel.valor}
                    </div>
                    <div className="text-[11px] text-gray-500">
                      {selectedLevel.origen === 'manual'
                        ? 'Creado manualmente'
                        : 'Reconocido del plano'}
                    </div>
                  </div>

                  {!selectedPoly && (
                    <button
                      type="button"
                      onClick={clearSelection}
                      className="text-gray-400 hover:text-gray-700 transition"
                      aria-label="Deseleccionar"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </header>

                {(selectedLevel.asociaciones || []).length === 0 ? (
                  <div className="rounded-md px-2.5 py-1.5 text-[11px] bg-amber-50 text-amber-800">
                    Sin asociar: no genera pendiente hasta que se asocie a un
                    lado de una superficie.
                  </div>
                ) : (
                  <ul className="space-y-1">
                    {(selectedLevel.asociaciones || []).map((a) => (
                      <li
                        key={`${a.id_poligono}-${a.lado}`}
                        className="flex items-center gap-1.5 text-gray-700"
                      >
                        <Link className="w-3 h-3 text-emerald-600 shrink-0" />
                        <span className="truncate">
                          {a.id_poligono} · lado {a.lado}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {selectedPoly ? (
                  <button
                    type="button"
                    onClick={handleAssociateLevel}
                    disabled={toolsLocked || !!mode}
                    className="w-full px-3 py-2 rounded-md bg-brand-blue hover:bg-brand-hover text-white text-[11px] font-semibold flex items-center justify-center gap-1.5 transition disabled:opacity-40 disabled:pointer-events-none"
                  >
                    <Link className="w-3.5 h-3.5" />
                    {selectedSide !== null
                      ? `Asociar al lado ${selectedSide}`
                      : 'Asociar al lado más cercano'}
                  </button>
                ) : (
                  <div className="text-[11px] text-gray-500">
                    Para asociarlo, seleccione también una superficie.
                  </div>
                )}

                <div className="grid grid-cols-2 gap-1.5">
                  <ActionButton
                    icon={Pencil}
                    disabled={toolsLocked || !!mode}
                    onClick={() => openEditLevel(selectedLevel)}
                  >
                    Editar valor
                  </ActionButton>

                  <ActionButton
                    icon={Unlink}
                    disabled={
                      toolsLocked ||
                      !!mode ||
                      (selectedLevel.asociaciones || []).length === 0
                    }
                    onClick={handleDisassociateLevel}
                  >
                    Desasociar
                  </ActionButton>
                </div>

                <ActionButton
                  icon={Trash2}
                  variant="danger"
                  disabled={toolsLocked || !!mode}
                  onClick={handleDeleteLevel}
                >
                  Eliminar nivel
                </ActionButton>

              </section>
            )}

          </aside>
        )}


        {/* ---------- ZOOM / VISTA ---------- */}

        <div className="absolute right-3 bottom-3 z-20 flex items-center gap-0.5 p-1 bg-white/95 backdrop-blur rounded-xl border border-gray-200 shadow-lg">

          <IconButton icon={ZoomOut} label="Alejar" onClick={() => zoomFromCenter(1 / 1.25)} />

          <button
            type="button"
            onClick={resetView}
            title="Ajustar a la pantalla (F)"
            className="min-w-[48px] px-1 h-8 rounded-md text-[11px] font-semibold text-gray-700 hover:bg-blue-50 transition tabular-nums"
          >
            {Math.round(view.zoom * 100)}%
          </button>

          <IconButton icon={ZoomIn} label="Acercar" onClick={() => zoomFromCenter(1.25)} />

          <div className="w-px h-5 bg-gray-200 mx-1" />

          <IconButton icon={Scan} label="Ajustar a la pantalla (F)" onClick={resetView} />

          <IconButton
            icon={isFullscreen ? Minimize : Maximize}
            label={isFullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}
            onClick={toggleFullscreen}
          />

        </div>


        {/* ---------- LEYENDA ---------- */}

        <div className="absolute left-3 bottom-3 z-20 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 max-w-[60%] bg-white/90 backdrop-blur rounded-xl border border-gray-200 shadow text-[11px] text-gray-600">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.levelLinked }} />
            Nivel asociado
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.levelFree }} />
            Sin asociar
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.polySelected }} />
            Seleccionado
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-1 rounded-sm" style={{ background: COLORS.sideSelected }} />
            Lado elegido
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-1 rounded-sm" style={{ background: COLORS.sideLinked }} />
            Lado con nivel
          </span>
        </div>


        {/* ---------- CONTENIDO ---------- */}

        {loading ? (

          <div className="flex flex-col items-center justify-center text-gray-500 py-10">
            <Loader2 className="w-8 h-8 animate-spin mb-2" />
            <span className="text-xs">Cargando elementos geométricos...</span>
          </div>

        ) : (

          <>

            {/* Con geometría vacía el Stage sigue activo para poder dibujar. */}
            {isEmptyGeometry && !mode && !draft && (
              <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none">
                <div className="flex flex-col items-center justify-center py-8 px-6 text-center text-amber-800 bg-amber-50/95 rounded-xl max-w-md border border-amber-200 shadow-sm">
                  <HelpCircle className="w-10 h-10 text-amber-500 mb-2" />
                  <h4 className="font-semibold text-sm">
                    No se reconoció geometría
                  </h4>
                  <p className="text-xs text-gray-600 mt-1">
                    Dibuje un triángulo (T) o un rectángulo (R) desde la
                    paleta de la izquierda para empezar.
                  </p>
                </div>
              </div>
            )}

            <Stage
              width={stageDimensions.width}
              height={stageDimensions.height}
              onWheel={handleWheel}
              onMouseDown={handlePointerDown}
              onMouseMove={handlePointerMove}
              onMouseUp={handlePointerUp}
              onMouseLeave={handlePointerUp}
              onClick={handleStageClick}
              style={{ cursor: canvasCursor }}
            >

              <Layer>

                {/* ---- LÍNEAS DE FONDO (solo dibujo, sin eventos) ---- */}

                {lineas.map((line, index) => {
                  const [x1, y1, x2, y2] = getLinePoints(line);
                  const [sx1, sy1] = transformPoint(x1, y1);
                  const [sx2, sy2] = transformPoint(x2, y2);

                  return (
                    <Line
                      key={`line-${index}`}
                      points={[sx1, sy1, sx2, sy2]}
                      stroke={line.color || '#94a3b8'}
                      strokeWidth={1}
                      dash={[4, 4]}
                      listening={false}
                    />
                  );
                })}


                {/* ---- POLÍGONOS ---- */}

                {orderedPolys.map((poly) => {
                  const points = normalizePoints(poly.puntos);

                  const screenPoints = points.flatMap((p) =>
                    transformPoint(p.x, p.y)
                  );

                  const isSelected =
                    selectedPolyId !== null &&
                    String(selectedPolyId) === String(poly.id);

                  const isHover =
                    !isSelected &&
                    hoverPolyId !== null &&
                    String(hoverPolyId) === String(poly.id);

                  const stroke = isSelected
                    ? COLORS.polySelected
                    : COLORS.poly;

                  return (
                    <Group key={poly.id}>

                      <Line
                        points={screenPoints}
                        closed
                        fill={
                          isSelected
                            ? '#d946ef33'
                            : isHover
                              ? '#1a6dba44'
                              : '#1a6dba22'
                        }
                        stroke={stroke}
                        strokeWidth={isSelected ? 3 : isHover ? 2.5 : 2}
                        hitStrokeWidth={10}
                        listening={!mode}
                        onMouseEnter={() => hoverOn(poly.id)}
                        onMouseLeave={hoverOff}
                        onClick={(e) => handlePolygonClick(e, poly)}
                        onDblClick={(e) => {
                          e.cancelBubble = true;

                          if (!isSelected) {
                            return;
                          }

                          const p = pointerToPlan(e.target.getStage());

                          if (p) {
                            handleAddVertex(poly, p[0], p[1]);
                          }
                        }}
                      />

                      {/* ---- LADOS (solo de la superficie seleccionada) ---- */}

                      {isSelected &&
                        points.map((a, i) => {
                          const b = points[(i + 1) % points.length];

                          const [ax, ay] = transformPoint(a.x, a.y);
                          const [bx, by] = transformPoint(b.x, b.y);

                          const linked = linkedSides.has(i);
                          const chosen = selectedSide === i;

                          const len = formatMeters(sideLength(a, b));

                          const label = linked
                            ? `L${i} · ${len} · ${linkedSides.get(i).join(' / ')}`
                            : `L${i} · ${len}`;

                          const w = Math.max(24, label.length * 5.6 + 10);

                          return (
                            <Group key={`side-${poly.id}-${i}`} listening={false}>

                              {(linked || chosen) && (
                                <Line
                                  points={[ax, ay, bx, by]}
                                  stroke={
                                    chosen
                                      ? COLORS.sideSelected
                                      : COLORS.sideLinked
                                  }
                                  strokeWidth={chosen ? 5 : 4}
                                  opacity={0.9}
                                  lineCap="round"
                                />
                              )}

                              <Group x={(ax + bx) / 2} y={(ay + by) / 2}>
                                <Rect
                                  x={-w / 2}
                                  y={-7}
                                  width={w}
                                  height={14}
                                  fill={chosen ? '#fef3c7' : '#ffffffdd'}
                                  cornerRadius={3}
                                />
                                <Text
                                  text={label}
                                  x={-w / 2}
                                  y={-7}
                                  width={w}
                                  height={14}
                                  align="center"
                                  verticalAlign="middle"
                                  fontSize={9}
                                  fill={chosen ? '#b45309' : '#334155'}
                                  fontStyle={chosen ? 'bold' : 'normal'}
                                />
                              </Group>

                            </Group>
                          );
                        })}

                      {/* ---- VÉRTICES ---- */}

                      {points.map((p, vertexIndex) => {
                        const [sx, sy] = transformPoint(p.x, p.y);

                        const vertexSelected =
                          isSelected && selectedVertex === vertexIndex;

                        return (
                          <Circle
                            key={`vertex-${poly.id}-${vertexIndex}`}
                            x={sx}
                            y={sy}
                            radius={vertexSelected ? 7 : isSelected ? 5.5 : 4}
                            fill={vertexSelected ? COLORS.sideSelected : stroke}
                            stroke="#fff"
                            strokeWidth={1.5}
                            opacity={isSelected || isHover ? 1 : 0.75}
                            draggable
                            listening={!mode}
                            onMouseEnter={() => hoverOn(poly.id)}
                            onMouseLeave={hoverOff}
                            onClick={(e) => {
                              e.cancelBubble = true;

                              setSelectedPolyId(poly.id);
                              setSelectedVertex(vertexIndex);
                            }}
                            onDragStart={() => {
                              draggingVertexRef.current = true;

                              setSelectedPolyId(poly.id);
                              setSelectedVertex(vertexIndex);
                            }}
                            onDragMove={(e) =>
                              handleVertexDrag(
                                poly.id,
                                vertexIndex,
                                e.target.x(),
                                e.target.y()
                              )
                            }
                            onDragEnd={(e) =>
                              handleVertexDragEnd(
                                poly,
                                vertexIndex,
                                e.target.x(),
                                e.target.y()
                              )
                            }
                            onDblClick={(e) => {
                              e.cancelBubble = true;

                              handleRemoveVertex(poly, vertexIndex);
                            }}
                          />
                        );
                      })}

                    </Group>
                  );
                })}


                {/* ---- SUPERFICIE EN CREACIÓN ---- */}

                {previewPoints.length > 0 && (
                  <Group listening={false}>

                    <Line
                      points={previewPoints.flatMap(([x, y]) =>
                        transformPoint(x, y)
                      )}
                      closed={previewPoints.length >= 3}
                      fill="#2a9d5c22"
                      stroke={COLORS.draft}
                      strokeWidth={2}
                      dash={[5, 5]}
                    />

                    {previewPoints.map(([x, y], index) => {
                      const [sx, sy] = transformPoint(x, y);

                      return (
                        <Circle
                          key={`new-point-${index}`}
                          x={sx}
                          y={sy}
                          radius={5}
                          fill={COLORS.draft}
                          stroke="#fff"
                          strokeWidth={1.5}
                        />
                      );
                    })}

                  </Group>
                )}


                {/* ---- CONEXIÓN NIVEL → LADO ASOCIADO ---- */}

                {cotasAltura.flatMap((level) => {
                  const [lx, ly] = getLevelPosition(level);

                  return (level.asociaciones || []).map((a) => {
                    const poly = polyById.get(String(a.id_poligono));

                    if (!poly) {
                      return null;
                    }

                    const pts = normalizePoints(poly.puntos);
                    const side = Number(a.lado);

                    if (!(side >= 0 && side < pts.length)) {
                      return null;
                    }

                    const p1 = pts[side];
                    const p2 = pts[(side + 1) % pts.length];

                    const c = closestOnSegment(lx, ly, p1.x, p1.y, p2.x, p2.y);

                    const [sx1, sy1] = transformPoint(lx, ly);
                    const [sx2, sy2] = transformPoint(c.x, c.y);

                    return (
                      <Group
                        key={`link-${level.id}-${a.id_poligono}`}
                        listening={false}
                      >
                        <Line
                          points={[sx1, sy1, sx2, sy2]}
                          stroke={COLORS.sideLinked}
                          strokeWidth={1.5}
                          dash={[4, 3]}
                        />
                        <Circle
                          x={sx2}
                          y={sy2}
                          radius={3.5}
                          fill={COLORS.sideLinked}
                          stroke="#fff"
                          strokeWidth={1}
                        />
                      </Group>
                    );
                  });
                })}


                {/* ---- NIVELES ---- */}

                {cotasAltura.map((level) => {
                  const [x, y] = getLevelPosition(level);
                  const [sx, sy] = transformPoint(x, y);

                  const isSelected =
                    selectedLevelId !== null &&
                    String(selectedLevelId) === String(level.id);

                  const linked =
                    level.asociado === true ||
                    (level.asociaciones || []).length > 0;

                  const label =
                    level.texto ?? formatLevelText(Number(level.valor));

                  const w = Math.max(48, String(label).length * 6.4 + 14);
                  const h = 20;

                  const fill = isSelected
                    ? COLORS.levelSelected
                    : linked
                      ? COLORS.levelLinked
                      : COLORS.levelFree;

                  return (
                    <Group
                      key={level.id}
                      x={sx}
                      y={sy}
                      listening={!mode}
                      onMouseEnter={() => hoverOn(null)}
                      onMouseLeave={hoverOff}
                      onClick={(e) => {
                        e.cancelBubble = true;

                        // Se conserva la superficie seleccionada para poder
                        // asociar ambos.
                        setSelectedLevelId(level.id);
                      }}
                      onDblClick={(e) => {
                        e.cancelBubble = true;

                        openEditLevel(level);
                      }}
                    >

                      <Rect
                        x={-w / 2}
                        y={-h / 2}
                        width={w}
                        height={h}
                        fill={fill}
                        stroke="#fff"
                        strokeWidth={isSelected ? 2 : 1}
                        cornerRadius={4}
                        shadowColor="#0f172a"
                        shadowBlur={isSelected ? 8 : 4}
                        shadowOpacity={0.25}
                        shadowOffsetY={1}
                      />

                      <Text
                        text={String(label)}
                        x={-w / 2}
                        y={-h / 2}
                        width={w}
                        height={h}
                        align="center"
                        verticalAlign="middle"
                        fontSize={10}
                        fontStyle="bold"
                        fill="#fff"
                      />

                    </Group>
                  );
                })}


                {/* ---- MEDICIÓN TEMPORAL ---- */}

                {measure.points.length > 0 && (() => {
                  const A = measure.points[0];
                  const B = measure.points[1] ?? measure.hover;

                  const [sax, say] = transformPoint(A[0], A[1]);

                  // Solo el primer punto: todavía no hay segmento.
                  if (!B) {
                    return (
                      <Circle
                        x={sax}
                        y={say}
                        radius={5}
                        fill={COLORS.measure}
                        stroke="#fff"
                        strokeWidth={1.5}
                        listening={false}
                      />
                    );
                  }

                  const [sbx, sby] = transformPoint(B[0], B[1]);
                  const [scx, scy] = transformPoint(A[0], B[1]); // esquina del triángulo

                  const dist = Math.hypot(B[0] - A[0], B[1] - A[1]);

                  // El eje y del plano es el horizontal en pantalla.
                  const horizontal = Math.abs(B[1] - A[1]);
                  const vertical = Math.abs(B[0] - A[0]);
                  const hasLegs =
                    horizontal > MIN_MEASURE_LEG && vertical > MIN_MEASURE_LEG;

                  return (
                    <Group listening={false}>

                      {hasLegs && (
                        <Line
                          points={[sax, say, scx, scy, sbx, sby]}
                          stroke={COLORS.measureLeg}
                          strokeWidth={1}
                          dash={[4, 3]}
                        />
                      )}

                      <Line
                        points={[sax, say, sbx, sby]}
                        stroke={COLORS.measure}
                        strokeWidth={2}
                      />

                      {[[sax, say], [sbx, sby]].map(([px, py], i) => (
                        <Circle
                          key={`measure-end-${i}`}
                          x={px}
                          y={py}
                          radius={5}
                          fill={COLORS.measure}
                          stroke="#fff"
                          strokeWidth={1.5}
                        />
                      ))}

                      {hasLegs && (
                        <>
                          <MeasureLabel
                            x={(sax + scx) / 2}
                            y={(say + scy) / 2 + (sby > say ? -13 : 13)}
                            text={formatMeters(horizontal)}
                            color={COLORS.measureLeg}
                          />
                          <MeasureLabel
                            x={(scx + sbx) / 2 + (sax < sbx ? 30 : -30)}
                            y={(scy + sby) / 2}
                            text={formatMeters(vertical)}
                            color={COLORS.measureLeg}
                          />
                        </>
                      )}

                      <MeasureLabel
                        x={(sax + sbx) / 2}
                        y={(say + sby) / 2}
                        text={formatMeters(dist)}
                        bold
                      />

                    </Group>
                  );
                })()}

              </Layer>

            </Stage>

          </>

        )}

      </div>


      {/* ====================================================
          RESUMEN + CONFIRMAR
      ==================================================== */}

      <div className="flex flex-wrap items-center gap-2 bg-white border border-gray-200 rounded-xl px-3.5 py-3 shadow-sm">

        <StatChip>{poligonos.length} superficies</StatChip>

        <StatChip tone={linkedLevels === cotasAltura.length && cotasAltura.length > 0 ? 'good' : 'neutral'}>
          {cotasAltura.length} niveles ({linkedLevels} asociados)
        </StatChip>

        <StatChip title="Líneas de referencia del plano">
          {lineas.length} líneas
        </StatChip>

        <StatChip>{capas.length} capas</StatChip>

        {withoutSlope > 0 && (
          <StatChip
            tone="warn"
            title="Cada superficie necesita dos niveles asociados a lados distintos"
          >
            {withoutSlope} sin pendiente
          </StatChip>
        )}

        <div className="flex-1" />

        <button
          type="button"
          onClick={handleConfirmGeometry}
          disabled={busy || !idModelo2D}
          className={`px-5 py-2.5 font-bold rounded-lg text-xs flex items-center gap-1.5 transition shadow-sm disabled:opacity-50 ${isValidated
              ? 'bg-emerald-50 text-emerald-700 border border-emerald-300 hover:bg-emerald-100'
              : 'bg-brand-blue hover:bg-brand-hover text-white'
            }`}
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCircle className="w-4 h-4" />
          )}

          {isValidated ? 'Geometría confirmada' : 'Confirmar geometría'}
        </button>

        {isValidated && (
          <button
            type="button"
            onClick={handleGenerate3D}
            disabled={busy || !idModelo2D}
            className="animate-fade-in px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg text-xs flex items-center gap-1.5 transition shadow-sm disabled:opacity-50"
          >
            {generating ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : null}
            {generating ? 'Generando 3D...' : 'Siguiente paso: Modelo 3D'}
            {!generating && <ArrowRight className="w-4 h-4" />}
          </button>
        )}

      </div>


      {/* ====================================================
          DIÁLOGO: VALOR DEL NIVEL
      ==================================================== */}

      {levelDialog && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) setLevelDialog(null);
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Valor del nivel"
            className="animate-fade-in w-full max-w-sm bg-white rounded-xl shadow-2xl border border-gray-200 p-5 space-y-4"
          >
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center shrink-0">
                <CirclePlus className="w-5 h-5" />
              </div>

              <div>
                <h3 className="font-semibold text-sm text-gray-900">
                  {levelDialog.kind === 'create'
                    ? 'Nuevo nivel'
                    : 'Editar nivel'}
                </h3>
                <p className="text-xs text-gray-500 mt-0.5">
                  {levelDialog.kind === 'create'
                    ? 'Escriba la cota y luego haga clic en el plano para ubicarla.'
                    : 'Escriba el nuevo valor de la cota.'}
                </p>
              </div>
            </div>

            <div>
              <label
                htmlFor="nivel-valor"
                className="block text-xs font-medium text-gray-700 mb-1.5"
              >
                Valor (en metros)
              </label>

              <input
                id="nivel-valor"
                autoFocus
                type="text"
                inputMode="decimal"
                placeholder="+7.90"
                value={levelDialog.value}
                onChange={(e) =>
                  setLevelDialog({
                    ...levelDialog,
                    value: e.target.value,
                    error: '',
                  })
                }
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    confirmLevelDialog();
                  }
                }}
                className={`w-full px-3 py-2 rounded-lg border text-sm focus:outline-none focus:ring-2 transition ${levelDialog.error
                    ? 'border-red-300 focus:ring-red-200'
                    : 'border-gray-300 focus:ring-blue-200 focus:border-brand-blue'
                  }`}
              />

              <div className="mt-1.5 text-[11px] min-h-[16px]">
                {levelDialog.error ? (
                  <span className="text-red-600">{levelDialog.error}</span>
                ) : levelPreview ? (
                  <span className="text-gray-500">
                    Se mostrará como{' '}
                    <strong className="text-gray-800">{levelPreview}</strong>
                  </span>
                ) : (
                  <span className="text-gray-400">
                    Acepta +7.90, 7,9, -1.20 o 7.9 m
                  </span>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setLevelDialog(null)}
                className="px-4 py-2 rounded-lg text-xs font-medium text-gray-700 border border-gray-300 hover:bg-gray-50 transition"
              >
                Cancelar
              </button>

              <button
                type="button"
                onClick={confirmLevelDialog}
                className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-blue hover:bg-brand-hover text-white transition"
              >
                {levelDialog.kind === 'create' ? 'Continuar' : 'Guardar'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};


export default GeometriaViewer;