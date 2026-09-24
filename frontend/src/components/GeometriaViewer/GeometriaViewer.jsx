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
  AlertTriangle,
  CheckCircle,
  Info,
  Loader2,
  HelpCircle,
  ZoomIn,
  ZoomOut,
  RefreshCw,
  Trash2,
  Ruler,
  Link,
  Unlink,
  Square,
  Triangle,
  Plus,
  Minus,
  X,
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
};


// ==========================================================
// UTILIDADES (funciones puras)
// ==========================================================
// <helpers>

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

/*
 * Punto de la recta a-b más cercano a (px, py), limitado al segmento.
 */
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

/*
 * "Lado" = arista i del polígono: va de puntos[i] a puntos[i + 1]
 * (el último lado cierra con el primer punto). Es el mismo criterio
 * que usa el backend.
 */
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

/*
 * Acepta "+7.90", "7,9", "-1.2", "−1.20", "±0.00", "7.9 m".
 * Devuelve null si no es un número válido.
 */
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
    return [
      Number(line.x1),
      Number(line.y1),
      Number(line.x2),
      Number(line.y2),
    ];
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

// </helpers>


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
  //const [tank, setTank] = useState(null);

  // ========================================================
  // VISTA
  // ========================================================

  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const [stageDimensions, setStageDimensions] = useState({
    width: 1200,
    height: 500,
  });

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
    null       → sin herramienta
    triangle   → creando triángulo (3 clics)
    rectangle  → creando rectángulo (2 clics)
    level      → colocando un nivel (1 clic)
    vertex     → agregando vértices a la superficie seleccionada
  */
  const [mode, setMode] = useState(null);

  // Puntos de la superficie que se está dibujando.
  const [draft, setDraft] = useState(null);
  const draftRef = useRef(null);

  // Valor del nivel que se va a colocar.
  const pendingLevelRef = useRef(null);


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
    ? cotasAltura.find(
        (l) => String(l.id) === String(selectedLevelId)
      ) || null
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
      setBoundingBox(data.bounding_box || null);
      // setTank(data.tank || null);
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


  // ========================================================
  // TRANSFORMACIÓN PLANO ↔ PANTALLA
  // ========================================================

  const getTransform = () => {
    const margin = 30;

    const cw = stageDimensions.width - margin * 2;
    const ch = stageDimensions.height - margin * 2;

    if (!boundingBox || boundingBox.min_x === undefined) {
      return {
        scale: zoom,
        offsetX: margin + pan.x,
        offsetY: margin + pan.y,
      };
    }

    const bboxWidth = Math.max(boundingBox.max_x - boundingBox.min_x, 1);
    const bboxHeight = Math.max(boundingBox.max_y - boundingBox.min_y, 1);

    const baseScale = Math.min(cw / bboxWidth, ch / bboxHeight);
    const scale = baseScale * zoom;

    const offsetX =
      margin +
      (cw - bboxWidth * scale) / 2 -
      boundingBox.min_x * scale +
      pan.x;

    const offsetY =
      margin +
      (ch - bboxHeight * scale) / 2 -
      boundingBox.min_y * scale +
      pan.y;

    return { scale, offsetX, offsetY };
  };

  const T = getTransform();

  /*
   * Se mantiene la inversión de ejes usada por el visor:
   * plano (x, y) → pantalla (y, x).
   */
  // const transformPoint = (x, y) => [
  //   y * T.scale + T.offsetX,
  //   x * T.scale + T.offsetY,
  // ];

  // const inverseTransformPoint = (screenX, screenY) => [
  //   (screenY - T.offsetY) / T.scale,
  //   (screenX - T.offsetX) / T.scale,
  // ];

  // const pointerToPlan = (stage) => {
  //   const pos = stage?.getPointerPosition();

  //   if (!pos) {
  //     return null;
  //   }

  //   return inverseTransformPoint(pos.x, pos.y);
  // };
  // T.rotation debe estar en radianes. 
// Ejemplo para 90 grados a la izquierda: T.rotation = -Math.PI / 2

  const transformPoint = (x, y) => [
    y * T.scale + T.offsetX,
    x * T.scale + T.offsetY,
  ];

  const inverseTransformPoint = (screenX, screenY) => {
    const x = (screenX - T.offsetX) / T.scale;
    const y = (screenY - T.offsetY) / T.scale;

    // Inversa de la rotación 90° antihoraria:
    // (x, y) -> (y, -x)
    return [
      y,
      x,
    ];
  };

  const pointerToPlan = (stage) => {
    const pos = stage?.getPointerPosition();

    if (!pos) {
      return null;
    }

    return inverseTransformPoint(pos.x, pos.y);
  };

  // ========================================================
  // ZOOM Y PAN
  // ========================================================

  const handleWheel = (e) => {
    e.evt.preventDefault();

    const factor = e.evt.deltaY < 0 ? 1.12 : 0.89;

    setZoom((z) => Math.max(0.3, Math.min(20, z * factor)));
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

      lastPointerPos.current = {
        x: e.evt.clientX,
        y: e.evt.clientY,
      };
    }
  };

  const handlePointerMove = (e) => {
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

    setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
  };

  const handlePointerUp = () => {
    isDraggingPan.current = false;
  };

  const resetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };


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
  };

  // Esc cancela la herramienta activa.
  useEffect(() => {
    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        setMode(null);

        draftRef.current = null;
        setDraft(null);

        pendingLevelRef.current = null;
      }
    };

    window.addEventListener('keydown', onKeyDown);

    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);


  // ========================================================
  // CAPA PARA SUPERFICIES NUEVAS
  // ========================================================

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

    draftRef.current = { kind, points: [] };
    setDraft({ kind, points: [] });

    setMode(kind);
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

  const handleCreateLevel = () => {
    if (!idModelo2D) {
      return;
    }

    const text = window.prompt('Ingrese el valor del nivel (ej. +7.90):');

    if (text === null) {
      return;
    }

    const valor = parseLevelValue(text);

    if (valor === null) {
      setError('El valor del nivel no es válido.');
      return;
    }

    setError(null);
    setInfo(null);

    pendingLevelRef.current = { valor };
    setMode('level');
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
        'Seleccione una superficie, elija su lado y presione «Asociar nivel».'
      );
    }
  };

  const handleUpdateLevel = async (level) => {
    if (!level?.id || !idModelo2D) {
      return;
    }

    const text = window.prompt('Nuevo valor del nivel:', String(level.valor));

    if (text === null) {
      return;
    }

    const valor = parseLevelValue(text);

    if (valor === null) {
      setError('El valor ingresado no es válido.');
      return;
    }

    await runMutation(
      () =>
        planosApi.updateNivel(idModelo2D, level.id, {
          valor,
          texto: formatLevelText(valor),
        }),
      'No se pudo actualizar el nivel.'
    );
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
  // (iguales para triángulos, rectángulos y reconocidos)
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
      const near = nearestSide(poly.puntos, p[0], p[1]);
      setSelectedSide(near ? near.side : null);
    }
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
  // RESIZE
  // ========================================================

  useEffect(() => {
    const updateSize = () => {
      if (!containerRef.current) {
        return;
      }

      setStageDimensions({
        width: containerRef.current.clientWidth || 1200,
        height: 500,
      });
    };

    updateSize();

    window.addEventListener('resize', updateSize);

    return () => window.removeEventListener('resize', updateSize);
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

  // La superficie seleccionada se dibuja al final (queda arriba).
  const orderedPolys = selectedPoly
    ? [
        ...poligonos.filter((p) => String(p.id) !== String(selectedPoly.id)),
        selectedPoly,
      ]
    : poligonos;

  const isEmptyGeometry =
    !loading && poligonos.length === 0 && lineas.length === 0;

  const toolsLocked = busy || !!mode;

  const roleOf = (poly, levelId) => {
    const id = String(levelId);

    if (poly.nivel_bajo && String(poly.nivel_bajo.id) === id) return 'bajo';
    if (poly.nivel_alto && String(poly.nivel_alto.id) === id) return 'alto';
    if (poly.nivel_medio && String(poly.nivel_medio.id) === id) return 'medio';

    return '—';
  };

  const pendienteText = (poly) => {
    const p = poly?.pendiente;

    if (p?.definida) {
      return `definida · desnivel ${Number(p.desnivel).toFixed(2)} m`;
    }

    return 'sin definir (se necesitan dos niveles en lados distintos)';
  };


  // ========================================================
  // RENDER
  // ========================================================

  return (

    <div className="space-y-4">


      {/* ====================================================
          CABECERA
      ==================================================== */}

      <div className="p-3 bg-amber-50 border border-amber-200 text-amber-900 rounded-md flex items-start gap-2 text-xs">

        <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />

        <div>

          <strong>CORRECTOR 2D INTERACTIVO:</strong>

          <div className="mt-1">
            Puede modificar la geometría reconocida, agregar o quitar
            vértices, agregar superficies y asociar niveles al lado de una
            superficie para generar su pendiente.
          </div>

        </div>

      </div>


      {/* ====================================================
          ERROR / INFO
      ==================================================== */}

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md text-xs">
          {error}
        </div>
      )}

      {info && !error && (
        <div className="p-3 bg-blue-50 border border-blue-200 text-blue-800 rounded-md text-xs flex items-start gap-2">
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{info}</span>
        </div>
      )}


      {/* ====================================================
          TOOLBAR
      ==================================================== */}

      <div className="bg-white border border-gray-200 rounded-md p-3 shadow-sm">

        <div className="flex flex-wrap items-center gap-2">

          {/* ---------- AGREGAR SUPERFICIE ---------- */}

          <span className="text-xs font-semibold text-gray-600 mr-1">
            Agregar superficie:
          </span>

          <button
            type="button"
            onClick={() => startSurface('triangle')}
            disabled={busy}
            className={`px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 ${
              mode === 'triangle' || draft?.kind === 'triangle'
                ? 'bg-brand-blue text-white border-brand-blue'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Triangle className="w-3.5 h-3.5" />
            Triángulo
          </button>

          <button
            type="button"
            onClick={() => startSurface('rectangle')}
            disabled={busy}
            className={`px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 ${
              mode === 'rectangle' || draft?.kind === 'rectangle'
                ? 'bg-brand-blue text-white border-brand-blue'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
            }`}
          >
            <Square className="w-3.5 h-3.5" />
            Rectángulo
          </button>

          {mode && (
            <button
              type="button"
              onClick={cancelMode}
              className="px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 text-red-700 border-red-300 hover:bg-red-50"
            >
              <X className="w-3.5 h-3.5" />
              {mode === 'vertex' ? 'Listo' : 'Cancelar'}
            </button>
          )}

          <div className="h-5 w-px bg-gray-300 mx-2" />

          {/* ---------- NIVEL ---------- */}

          <button
            type="button"
            onClick={handleCreateLevel}
            disabled={toolsLocked || !idModelo2D}
            className="px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 bg-white text-gray-700 border-gray-300 hover:bg-gray-50 disabled:opacity-50"
          >
            <Ruler className="w-3.5 h-3.5" />
            Agregar nivel
          </button>

          {selectedLevel && (
            <button
              type="button"
              onClick={handleDeleteLevel}
              disabled={toolsLocked}
              className="px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 text-red-700 border-red-300 hover:bg-red-50 disabled:opacity-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Eliminar nivel
            </button>
          )}

          {/* ---------- SUPERFICIE SELECCIONADA ---------- */}

          {selectedPoly && (
            <>
              <div className="h-5 w-px bg-gray-300 mx-2" />

              <span className="text-xs font-semibold text-gray-600 mr-1">
                Superficie:
              </span>

              <button
                type="button"
                onClick={toggleVertexMode}
                disabled={busy || (!!mode && mode !== 'vertex')}
                className={`px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 disabled:opacity-50 ${
                  mode === 'vertex'
                    ? 'bg-brand-blue text-white border-brand-blue'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
                title="Haga clic sobre un lado de la superficie para insertar un vértice"
              >
                <Plus className="w-3.5 h-3.5" />
                Agregar vértice
              </button>

              <button
                type="button"
                onClick={() => handleRemoveVertex(selectedPoly, selectedVertex)}
                disabled={toolsLocked || selectedVertex === null}
                className="px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 bg-white text-gray-700 border-gray-300 hover:bg-gray-50 disabled:opacity-50"
                title="Seleccione un vértice (clic) y presione este botón, o haga doble clic sobre él"
              >
                <Minus className="w-3.5 h-3.5" />
                Eliminar vértice
              </button>

              <button
                type="button"
                onClick={handleDeletePolygon}
                disabled={toolsLocked}
                className="px-3 py-1.5 rounded text-xs font-medium border flex items-center gap-1.5 text-red-700 border-red-300 hover:bg-red-50 disabled:opacity-50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Eliminar superficie
              </button>
            </>
          )}

          <div className="flex-1" />

          {busy && (
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Guardando...
            </span>
          )}

          {/* ---------- ZOOM ---------- */}

          <button
            type="button"
            onClick={() => setZoom((z) => Math.min(6, z * 1.2))}
            className="p-1.5 bg-white border border-gray-300 rounded"
            title="Acercar"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={() => setZoom((z) => Math.max(0.3, z * 0.8))}
            className="p-1.5 bg-white border border-gray-300 rounded"
            title="Alejar"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={resetView}
            className="p-1.5 bg-white border border-gray-300 rounded"
            title="Restablecer vista"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>

        </div>


        {/* ---------- ASOCIACIONES ---------- */}

        <div className="flex flex-wrap items-center gap-2 mt-3 pt-3 border-t border-gray-100">

          <span className="text-xs font-semibold text-gray-600 mr-1">
            Niveles:
          </span>

          <button
            type="button"
            onClick={handleAssociateLevel}
            disabled={toolsLocked || !selectedPoly || !selectedLevel}
            className="px-3 py-1.5 rounded text-xs border bg-white hover:bg-gray-50 disabled:opacity-50 flex items-center gap-1.5"
            title="Seleccione una superficie (se marca su lado más cercano al clic) y un nivel"
          >
            <Link className="w-3.5 h-3.5" />
            {selectedSide !== null && selectedPoly
              ? `Asociar nivel al lado ${selectedSide}`
              : 'Asociar nivel'}
          </button>

          <button
            type="button"
            onClick={handleDisassociateLevel}
            disabled={
              toolsLocked ||
              !selectedLevel ||
              (selectedLevel.asociaciones || []).length === 0
            }
            className="px-3 py-1.5 rounded text-xs border bg-white hover:bg-gray-50 disabled:opacity-50 flex items-center gap-1.5"
          >
            <Unlink className="w-3.5 h-3.5" />
            Desasociar
          </button>

          <div className="flex-1" />

          {/* ---------- LEYENDA ---------- */}

          <div className="flex flex-wrap items-center gap-3 text-[11px] text-gray-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.levelLinked }} />
              Nivel asociado
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.levelFree }} />
              Nivel sin asociar
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded-sm" style={{ background: COLORS.polySelected }} />
              Seleccionado
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-1 rounded-sm" style={{ background: COLORS.sideSelected }} />
              Lado elegido
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-1 rounded-sm" style={{ background: COLORS.sideLinked }} />
              Lado con nivel
            </span>
          </div>

        </div>

      </div>


      {/* ====================================================
          INSTRUCCIÓN
      ==================================================== */}

      {mode ? (

        <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-xs text-blue-800">

          {mode === 'triangle' && (
            <>
              <strong>Triángulo:</strong> haga clic en 3 puntos del plano (
              {draft?.points.length ?? 0}/3). La superficie se creará
              automáticamente. Esc cancela.
            </>
          )}

          {mode === 'rectangle' && (
            <>
              <strong>Rectángulo:</strong> haga clic en una esquina y luego en
              la esquina opuesta ({draft?.points.length ?? 0}/2). Esc cancela.
            </>
          )}

          {mode === 'level' && (
            <>
              <strong>Nivel:</strong> haga clic sobre el punto donde desea
              colocarlo. Si hay una superficie cerca se asocia sola a su lado
              más cercano. Esc cancela.
            </>
          )}

          {mode === 'vertex' && (
            <>
              <strong>Agregar vértice:</strong> haga clic sobre un lado de la
              superficie seleccionada; puede agregar varios. Presione «Listo» o
              Esc para terminar.
            </>
          )}

        </div>

      ) : (

        <div className="text-[11px] text-gray-500">
          Clic en una superficie: la selecciona y marca su lado más cercano ·
          clic en un nivel: lo selecciona · arrastre un vértice para moverlo ·
          doble clic sobre el borde de la superficie seleccionada: agrega un
          vértice · doble clic sobre un vértice: lo elimina · doble clic en un
          nivel: cambia su valor.
        </div>

      )}


      {/* ====================================================
          CANVAS
      ==================================================== */}

      <div
        ref={containerRef}
        className="relative bg-slate-50 border border-gray-300 rounded-md flex items-center justify-center overflow-hidden"
        style={{ minHeight: 500 }}
      >

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
                <div className="flex flex-col items-center justify-center py-8 px-6 text-center text-amber-800 bg-amber-50/90 rounded-lg max-w-md border border-amber-200">
                  <HelpCircle className="w-10 h-10 text-amber-500 mb-2" />
                  <h4 className="font-semibold text-sm">
                    No se reconoció geometría
                  </h4>
                  <p className="text-xs text-gray-600 mt-1">
                    Puede crear un triángulo o un rectángulo manualmente.
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
              onClick={handleStageClick}
              style={{ cursor: mode ? 'crosshair' : 'default' }}
            >

              <Layer>

                {/* =============================================
                    LÍNEAS DE FONDO (solo dibujo, sin eventos)
                ============================================= */}

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
                {/* =============================================
                    TANQUE
                ============================================= */}

                {/* {tank && (
                  (() => {
                    const tx = Number(tank.x ?? 0);
                    const ty = Number(tank.y ?? 0);
                    const width = Number(tank.width ?? 0);
                    const depth = Number(tank.depth ?? 0);

                    const x1 = tx - width / 2;
                    const y1 = ty - depth / 2;
                    const x2 = tx + width / 2;
                    const y2 = ty + depth / 2;

                    const [sx1, sy1] = transformPoint(x1, y1);
                    const [sx2, sy2] = transformPoint(x2, y2);

                    return (
                      <Line
                        points={[
                          sx1, sy1,
                          sx2, sy1,
                          sx2, sy2,
                          sx1, sy2,
                        ]}
                        closed
                        fill="#38bdf833"
                        stroke="#0284c7"
                        strokeWidth={2}
                        listening={false}
                      />
                    );
                  })()
                )} */}


                {/* =============================================
                    POLÍGONOS
                ============================================= */}

                {orderedPolys.map((poly) => {
                  const points = normalizePoints(poly.puntos);

                  const screenPoints = points.flatMap((p) =>
                    transformPoint(p.x, p.y)
                  );

                  const isSelected =
                    selectedPolyId !== null &&
                    String(selectedPolyId) === String(poly.id);

                  const stroke = isSelected
                    ? COLORS.polySelected
                    : COLORS.poly;

                  return (
                    <Group key={poly.id}>

                      <Line
                        points={screenPoints}
                        closed
                        fill={isSelected ? '#d946ef33' : '#1a6dba22'}
                        stroke={stroke}
                        strokeWidth={isSelected ? 3 : 2}
                        hitStrokeWidth={10}
                        listening={!mode}
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

                          const label = linked
                            ? `L${i} · ${linkedSides.get(i).join(' / ')}`
                            : `L${i}`;

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
                                  fill="#ffffffdd"
                                  cornerRadius={2}
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
                            radius={vertexSelected ? 7 : 5}
                            fill={vertexSelected ? COLORS.sideSelected : stroke}
                            stroke="#fff"
                            strokeWidth={1.5}
                            draggable
                            listening={!mode}
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


                {/* =============================================
                    SUPERFICIE EN CREACIÓN
                ============================================= */}

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
                        />
                      );
                    })}

                  </Group>
                )}


                {/* =============================================
                    CONEXIÓN NIVEL → LADO ASOCIADO
                ============================================= */}

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


                {/* =============================================
                    NIVELES
                ============================================= */}

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
                      onClick={(e) => {
                        e.cancelBubble = true;

                        // Se conserva la superficie seleccionada para poder
                        // asociar ambos.
                        setSelectedLevelId(level.id);
                      }}
                      onDblClick={(e) => {
                        e.cancelBubble = true;

                        handleUpdateLevel(level);
                      }}
                    >

                      <Rect
                        x={-w / 2}
                        y={-h / 2}
                        width={w}
                        height={h}
                        fill={fill}
                        stroke="#fff"
                        strokeWidth={1}
                        cornerRadius={3}
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

              </Layer>

            </Stage>

          </>

        )}

      </div>


      {/* ====================================================
          DETALLE DE LA SELECCIÓN
      ==================================================== */}

      <div className="grid gap-3 md:grid-cols-2 text-xs">

        <div className="bg-white border border-gray-200 rounded-md p-3">

          <div className="font-semibold text-gray-700 mb-1">
            Superficie seleccionada
          </div>

          {!selectedPoly ? (
            <div className="text-gray-500">
              Haga clic sobre una superficie.
            </div>
          ) : (
            <div className="space-y-1 text-gray-600">

              <div>
                <span className="text-gray-500">ID:</span> {selectedPoly.id}
                {selectedPoly.tipo ? ` · ${selectedPoly.tipo}` : ''}
                {' · '}
                {(selectedPoly.puntos || []).length} vértices
              </div>

              <div>
                <span className="text-gray-500">Lado elegido:</span>{' '}
                {selectedSide !== null ? selectedSide : 'ninguno'}
                {' · '}
                <span className="text-gray-500">Pendiente:</span>{' '}
                {pendienteText(selectedPoly)}
              </div>

              {(selectedPoly.niveles || []).length === 0 ? (
                <div className="text-gray-500">Sin niveles asociados.</div>
              ) : (
                <table className="w-full mt-1">
                  <thead>
                    <tr className="text-left text-gray-500">
                      <th className="font-medium pr-2">Lado</th>
                      <th className="font-medium pr-2">Nivel</th>
                      <th className="font-medium">Rol</th>
                    </tr>
                  </thead>
                  <tbody>
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

            </div>
          )}

        </div>

        <div className="bg-white border border-gray-200 rounded-md p-3">

          <div className="font-semibold text-gray-700 mb-1">
            Nivel seleccionado
          </div>

          {!selectedLevel ? (
            <div className="text-gray-500">Haga clic sobre un nivel.</div>
          ) : (
            <div className="space-y-1 text-gray-600">

              <div>
                <strong>{selectedLevel.texto ?? selectedLevel.valor}</strong>
                {' · '}
                {selectedLevel.origen === 'manual'
                  ? 'creado manualmente'
                  : 'reconocido del plano'}
              </div>

              {(selectedLevel.asociaciones || []).length === 0 ? (
                <div className="text-amber-700">
                  Sin asociar: no genera pendiente hasta que se asocie a un
                  lado de una superficie.
                </div>
              ) : (
                (selectedLevel.asociaciones || []).map((a) => (
                  <div key={`${a.id_poligono}-${a.lado}`}>
                    Asociado a {a.id_poligono} · lado {a.lado}
                  </div>
                ))
              )}

            </div>
          )}

        </div>

      </div>


      {/* ====================================================
          INFORMACIÓN
      ==================================================== */}

      <div className="text-xs text-gray-600 flex flex-wrap gap-4">

        <span>
          Superficies: <strong>{poligonos.length}</strong>
        </span>

        <span>
          Líneas: <strong>{lineas.length}</strong>
        </span>

        <span>
          Niveles: <strong>{cotasAltura.length}</strong>
          {' '}(
          {cotasAltura.filter((l) => (l.asociaciones || []).length > 0).length}
          {' '}asociados)
        </span>

        <span>
          Capas: <strong>{capas.length}</strong>
        </span>

      </div>


      {/* ====================================================
          CONFIRMAR
      ==================================================== */}

      <div className="flex justify-end gap-3 pt-2">

        <button
          type="button"
          onClick={handleConfirmGeometry}
          disabled={busy || !idModelo2D}
          className="px-5 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs flex items-center gap-1.5 disabled:opacity-50"
        >
          {saving ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <CheckCircle className="w-4 h-4" />
          )}

          {isValidated ? 'Geometría Confirmada ✓' : 'Confirmar Geometría'}
        </button>

        {isValidated && (
          <button
            type="button"
            onClick={handleGenerate3D}
            disabled={busy || !idModelo2D}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded text-xs flex items-center gap-1.5 disabled:opacity-50"
          >
            {generating && <Loader2 className="w-4 h-4 animate-spin" />}
            {generating ? 'Generando 3D...' : 'Siguiente paso (Modelo 3D) →'}
          </button>
        )}

      </div>

    </div>
  );
};


export default GeometriaViewer;