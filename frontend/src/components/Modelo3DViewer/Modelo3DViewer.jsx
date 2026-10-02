import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three-stdlib';
import {
  RefreshCw, Box, Loader2, Maximize2, Minimize2, X,
  ChevronDown, ChevronUp, AlertTriangle, Crosshair, RotateCw,
} from 'lucide-react';
import { modelos3dApi } from '../../api/modelos3d';
import { getMastColor } from '../../hooks/utilsMastilVisual';
import { buildCoberturaGroup, disposeGroup } from '../../hooks/coberturaSPDALayer';

/**
 * FARADYNE Model Convention:
 * El Backend Python envía: [x, y, z] donde Z es la altura.
 * Three.js usa Y como altura: X=x, Y=z, Z=-y.
 *
 * Interacción:
 *  - Arrastrar: rotar · Clic derecho / Shift+arrastrar: mover · Rueda: zoom
 *  - Pasar el mouse sobre una cubierta: ver su altura en ese punto
 *  - Clic: seleccionar cubierta · Doble clic: enfocarla
 */

// ============================================================
// CONSTANTES
// ============================================================

const EMPTY_MASTS = [];

const COLOR_SOLID = 0x38bdf8;
const COLOR_EDGE = 0x0284c7;
const COLOR_HOVER = 0x22d3ee;
const COLOR_SELECTED = 0xf59e0b;

// Azul (bajo) -> rojo (alto). Mismo mapeo que heightColor().
const LEGEND_GRADIENT = `linear-gradient(to top, ${[0, 0.25, 0.5, 0.75, 1]
  .map((t) => `hsl(${Math.round((1 - t) * 0.66 * 360)}, 85%, 52%)`)
  .join(', ')})`;

const TIPO_CUBIERTA_LABEL = {
  pendiente_por_resolver: 'Sin niveles (altura estimada)',
  nivel_medio_pendiente: 'Un solo nivel',
  pendiente_entre_niveles: 'Pendiente entre 2 niveles',
  pendiente_con_nivel_medio: 'Pendiente con nivel medio',
};

// ============================================================
// UTILIDADES
// ============================================================

const num = (v, fallback = null) => {
  if (v === null || v === undefined || v === '') return fallback;
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

const fmt = (v, d = 2) => (Number.isFinite(v) ? v.toFixed(d) : '—');

const formatLevel = (v) => {
  if (Math.abs(v) < 0.005) return '±0.00';
  return `${v > 0 ? '+' : '-'}${Math.abs(v).toFixed(2)}`;
};

const tipoLabel = (tipo) => TIPO_CUBIERTA_LABEL[tipo] || tipo || '—';

const toThree = (p) => new THREE.Vector3(p[0], p[2], -p[1]);

function heightColor(t) {
  const c = new THREE.Color();
  c.setHSL((1 - Math.min(Math.max(t, 0), 1)) * 0.66, 0.85, 0.52);
  return c;
}

function polygonArea(vertices) {
  if (!Array.isArray(vertices) || vertices.length < 3) return null;
  let sum = 0;
  for (let i = 0; i < vertices.length; i++) {
    const a = vertices[i];
    const b = vertices[(i + 1) % vertices.length];
    sum += a[0] * b[1] - b[0] * a[1];
  }
  return Math.abs(sum) / 2;
}

function disposeObject(obj) {
  obj.traverse((child) => {
    if (child.geometry && child.geometry.dispose) child.geometry.dispose();
    const mats = Array.isArray(child.material)
      ? child.material
      : child.material
        ? [child.material]
        : [];
    mats.forEach((m) => {
      if (m.map && m.map.dispose) m.map.dispose();
      if (m.dispose) m.dispose();
    });
  });
}

/** Límites del modelo y rango de alturas (solo caras superiores). */
function computeStats(prisms) {
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  let zMin = Infinity, zMax = -Infinity, zAll = 0;

  prisms.forEach((p) =>
    (p.faces || []).forEach((f) =>
      (f.points || []).forEach((pt) => {
        minX = Math.min(minX, pt[0]);
        maxX = Math.max(maxX, pt[0]);
        minY = Math.min(minY, pt[1]);
        maxY = Math.max(maxY, pt[1]);
        zAll = Math.max(zAll, pt[2]);
        if (f.type === 'top') {
          zMin = Math.min(zMin, pt[2]);
          zMax = Math.max(zMax, pt[2]);
        }
      })
    )
  );

  if (!Number.isFinite(minX)) {
    minX = 0; maxX = 80; minY = 0; maxY = 20;
  }
  if (!Number.isFinite(zMin)) {
    zMin = 0; zMax = 0;
  }

  return {
    minX, maxX, minY, maxY, zMin, zMax, zAll,
    size: Math.max(maxX - minX, maxY - minY, zAll, 10),
  };
}

/** Cotas con valor para rotular. Ignora marcas sin valor (símbolos). */
function collectLevelLabels(meta) {
  const out = [];
  const seen = new Set();

  const push = (val, x, y) => {
    if (val === null || x === null || y === null) return;
    const key = `${val.toFixed(2)}-${Math.round(x * 2)}-${Math.round(y * 2)}`;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({ val, x, y });
  };

  const marks = meta.level_marks || meta.cotas_altura || [];

  marks.forEach((m) => {
    const val = num(m.value ?? m.valor);
    const pos = Array.isArray(m.posicion) ? m.posicion : [m.posicion?.x, m.posicion?.y];
    push(val, num(m.x ?? pos[0]), num(m.y ?? pos[1]));
  });

  // Respaldo: niveles asociados a cada cubierta.
  if (!out.length) {
    (meta.regions || []).forEach((r) =>
      (r.niveles || []).forEach((n) =>
        push(num(n.valor ?? n.value), num(n.x), num(n.y))
      )
    );
  }

  return out;
}

function makeLabelSprite(text, width) {
  const cv = document.createElement('canvas');
  cv.width = 256;
  cv.height = 80;
  const ctx = cv.getContext('2d');
  if (!ctx) return null;

  ctx.fillStyle = 'rgba(255,255,255,.95)';
  ctx.strokeStyle = '#0284c7';
  ctx.lineWidth = 4;
  const r = 16;
  ctx.beginPath();
  ctx.moveTo(r, 2);
  ctx.lineTo(254 - r, 2);
  ctx.quadraticCurveTo(254, 2, 254, r);
  ctx.lineTo(254, 78 - r);
  ctx.quadraticCurveTo(254, 78, 254 - r, 78);
  ctx.lineTo(r, 78);
  ctx.quadraticCurveTo(2, 78, 2, 78 - r);
  ctx.lineTo(2, r);
  ctx.quadraticCurveTo(2, 2, r, 2);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 40px Arial';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 128, 42);

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(cv),
      transparent: true,
      depthTest: false,
    })
  );
  sprite.scale.set(width, (width * 80) / 256, 1);
  sprite.renderOrder = 10;
  return sprite;
}

function buildPrismMesh(prism, tOf, opacity) {
  if (!prism.faces || prism.faces.length === 0) return null;

  const positions = [];
  const colors = [];

  prism.faces.forEach((face) => {
    const pts = face.points;
    if (!pts || pts.length < 3) return;

    const v = pts.map(toThree);
    const zTop = Math.max(...pts.map((p) => p[2]));

    const colorOf = (p) => {
      if (face.type === 'top') return heightColor(tOf(p[2]));
      if (face.type === 'side') return heightColor(tOf(zTop)).multiplyScalar(0.7);
      return new THREE.Color(0x1e293b);
    };
    const c = pts.map(colorOf);

    for (let i = 1; i < v.length - 1; i++) {
      [0, i, i + 1].forEach((k) => {
        positions.push(v[k].x, v[k].y, v[k].z);
        colors.push(c[k].r, c[k].g, c[k].b);
      });
    }
  });

  if (!positions.length) return null;

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  geo.computeVertexNormals();

  const base = {
    transparent: true,
    opacity,
    side: THREE.DoubleSide,
    roughness: 0.65,
    metalness: 0.1,
  };
  const matSolid = new THREE.MeshStandardMaterial({ ...base, color: COLOR_SOLID });
  const matHeight = new THREE.MeshStandardMaterial({ ...base, vertexColors: true });

  const mesh = new THREE.Mesh(geo, matHeight);
  mesh.name = prism.id || 'roof_region';

  const edge = new THREE.LineSegments(
    new THREE.EdgesGeometry(geo),
    new THREE.LineBasicMaterial({ color: COLOR_EDGE, transparent: true, opacity: 0.6 })
  );
  mesh.add(edge);

  mesh.userData = { id: prism.id, matSolid, matHeight, edge };
  return mesh;
}

// ============================================================
// COMPONENTES PEQUEÑOS DE UI
// ============================================================

const Chip = ({ active, onClick, title, children }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    aria-pressed={active}
    className={`px-2 py-1 rounded border text-[11px] font-semibold transition ${active
        ? 'bg-slate-600 border-brand-blue text-white'
        : 'bg-slate-700/60 border-slate-600 text-slate-400 hover:text-white'
      }`}
  >
    {children}
  </button>
);

const ToolBtn = ({ onClick, title, children }) => (
  <button
    type="button"
    onClick={onClick}
    title={title}
    className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 hover:text-white rounded text-[11px] font-semibold flex items-center gap-1.5 transition"
  >
    {children}
  </button>
);

// ============================================================
// COMPONENTE PRINCIPAL
// ============================================================

export const Modelo3DViewer = ({
  idModelo2D,
  idModelo3D,
  masts = EMPTY_MASTS,
  coverageData = null,
}) => {
  const containerRef = useRef(null);
  const mountRef = useRef(null);
  const controlsRef = useRef(null);
  const cameraRef = useRef(null);
  const sceneRef = useRef(null);
  const groupsRef = useRef(null);
  const viewsRef = useRef(null);
  const animRef = useRef(null);
  const refreshHighlightRef = useRef(null);
  const focusRegionRef = useRef(null);
  const selectedIdRef = useRef(null);
  const requestRef = useRef(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [model3dData, setModel3dData] = useState(null);
  const [sceneVersion, setSceneVersion] = useState(0);

  // Cobertura SPDA
  const [showSuperficies, setShowSuperficies] = useState(true);
  const [showZonas, setShowZonas] = useState(true);

  // Visualización
  const [showLabels, setShowLabels] = useState(true);
  const [showGrid, setShowGrid] = useState(true);
  const [showEdges, setShowEdges] = useState(true);
  const [showMasts, setShowMasts] = useState(true);
  const [colorMode, setColorMode] = useState('altura'); // 'altura' | 'unico'
  const [opacity, setOpacity] = useState(0.85);
  const [autoRotate, setAutoRotate] = useState(false);

  // Interacción
  const [selectedId, setSelectedId] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [showHint, setShowHint] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // ----------------------------------------------------------
  // CARGA DEL MODELO
  // ----------------------------------------------------------

  const fetchModel = useCallback(async () => {
    if (!idModelo2D && !idModelo3D) return;

    const token = ++requestRef.current;
    setLoading(true);
    setError(null);
    setSelectedId(null);

    try {
      const data = idModelo3D
        ? await modelos3dApi.getModelo3D(idModelo3D)
        : await modelos3dApi.generateModelo3D({ id_modelo2d: idModelo2D });

      if (token === requestRef.current) setModel3dData(data);
    } catch (err) {
      console.error('Error cargando el modelo 3D:', err);
      if (token === requestRef.current) {
        setError('No se pudo cargar el modelo 3D. Revise la conexión e intente de nuevo.');
      }
    } finally {
      if (token === requestRef.current) setLoading(false);
    }
  }, [idModelo2D, idModelo3D]);

  useEffect(() => {
    fetchModel();
  }, [fetchModel]);

  // ----------------------------------------------------------
  // DATOS DERIVADOS PARA LA UI
  // ----------------------------------------------------------

  const meta = model3dData?.geometria_volumetrica || null;

  const regionList = useMemo(() => {
    const prisms = meta?.prisms || [];
    const regions = meta?.regions || [];

    return prisms.map((p) => {
      const r = regions.find((x) => x.id === p.id) || {};
      const pend = r.pendiente || {};
      const zlow = num(p.zlow);
      const zhigh = num(p.zhigh);

      return {
        id: p.id,
        zlow,
        zhigh,
        tipo: p.tipo_cubierta,
        niveles: p.niveles || [],
        desnivel: num(pend.desnivel, zlow !== null && zhigh !== null ? zhigh - zlow : null),
        plana: Boolean(pend.plana),
        area: polygonArea(p.top_vertices),
        sinNiveles: p.tipo_cubierta === 'pendiente_por_resolver',
      };
    });
  }, [meta]);

  const heightRange = useMemo(() => {
    const s = computeStats(meta?.prisms || []);
    return { zMin: s.zMin, zMax: s.zMax };
  }, [meta]);

  const selected = regionList.find((r) => r.id === selectedId) || null;

  // ----------------------------------------------------------
  // CÁMARA: ANIMACIÓN Y VISTAS
  // ----------------------------------------------------------

  const flyTo = useCallback((pos, target, duration = 650) => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    if (!camera || !controls) return;

    animRef.current = {
      fromPos: camera.position.clone(),
      toPos: pos.clone(),
      fromTarget: controls.target.clone(),
      toTarget: target.clone(),
      t0: performance.now(),
      duration,
    };
  }, []);

  const setView = (name) => {
    const v = viewsRef.current?.[name];
    if (v) flyTo(v.pos, v.target);
  };

  const handleReset = () => {
    setView('iso');
    setSelectedId(null);
  };

  const toggleFullscreen = () => {
    const el = containerRef.current;
    if (!el) return;
    if (document.fullscreenElement) {
      if (document.exitFullscreen) document.exitFullscreen();
    } else if (el.requestFullscreen) {
      el.requestFullscreen();
    }
  };

  useEffect(() => {
    const onChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // ----------------------------------------------------------
  // ESCENA (se reconstruye solo cuando cambia el modelo)
  // ----------------------------------------------------------

  useEffect(() => {
    const el = mountRef.current;
    if (!el || !model3dData) return undefined;

    const metaData = model3dData.geometria_volumetrica || {};
    const prisms = metaData.prisms || [];
    const stats = computeStats(prisms);
    const { size } = stats;

    const cx = (stats.minX + stats.maxX) / 2;
    const cy = (stats.minY + stats.maxY) / 2;
    const center = new THREE.Vector3(cx, stats.zAll * 0.4, -cy);

    const range = stats.zMax - stats.zMin;
    const tOf = (z) => (range > 1e-6 ? (z - stats.zMin) / range : 0.5);

    // --- Escena, cámara, renderer ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(
      45,
      el.clientWidth / Math.max(el.clientHeight, 1),
      0.1,
      Math.max(5000, size * 30)
    );
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);

    // --- Luces ---
    scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(center.x + size, size * 1.5, center.z + size * 0.5);
    sun.target.position.copy(center);
    scene.add(sun);
    scene.add(sun.target);

    // --- Cubiertas ---
    const roofGroup = new THREE.Group();
    roofGroup.name = 'roofs';
    const meshes = [];

    prisms.forEach((prism) => {
      const mesh = buildPrismMesh(prism, tOf, 0.85);
      if (mesh) {
        roofGroup.add(mesh);
        meshes.push(mesh);
      }
    });
    scene.add(roofGroup);

    // --- Tanque (si el backend lo envía) ---
    if (metaData.tank) {
      const t = metaData.tank;
      const tank = new THREE.Mesh(
        new THREE.BoxGeometry(t.width, t.top - t.base, t.depth),
        new THREE.MeshStandardMaterial({
          color: 0xe07a10, transparent: true, opacity: 0.85, roughness: 0.4,
        })
      );
      tank.position.set(t.x, (t.base + t.top) / 2, -t.y);
      roofGroup.add(tank);
    }

    // --- Cotas de nivel ---
    const labelsGroup = new THREE.Group();
    labelsGroup.name = 'labels';
    const labelWidth = Math.min(Math.max(size * 0.045, 1.4), 8);
    const poleVerts = [];

    collectLevelLabels(metaData).forEach(({ val, x, y }) => {
      const sprite = makeLabelSprite(formatLevel(val), labelWidth);
      if (!sprite) return;
      const yLabel = Math.max(val, 0) + 0.3;
      sprite.position.set(x, yLabel, -y);
      labelsGroup.add(sprite);
      poleVerts.push(x, 0, -y, x, yLabel, -y);
    });

    if (poleVerts.length) {
      const poleGeo = new THREE.BufferGeometry();
      poleGeo.setAttribute('position', new THREE.Float32BufferAttribute(poleVerts, 3));
      labelsGroup.add(
        new THREE.LineSegments(
          poleGeo,
          new THREE.LineBasicMaterial({ color: 0xfacc15, transparent: true, opacity: 0.35 })
        )
      );
    }
    scene.add(labelsGroup);

    // --- Grilla centrada en el modelo ---
    const gridSize = Math.ceil((size * 1.5) / 5) * 5;
    const grid = new THREE.GridHelper(
      gridSize,
      Math.max(2, Math.ceil(gridSize / 5)),
      0x38bdf8,
      0x334155
    );
    grid.position.set(cx, -0.01, -cy);
    scene.add(grid);

    groupsRef.current = { roof: roofGroup, labels: labelsGroup, grid, meshes };

    // --- Vistas predefinidas ---
    const dist = size * 1.6;
    const ground = new THREE.Vector3(cx, 0, -cy);
    viewsRef.current = {
      iso: {
        pos: center.clone().add(new THREE.Vector3(0.75, 0.6, 0.75).multiplyScalar(dist)),
        target: center.clone(),
      },
      top: {
        pos: new THREE.Vector3(cx, dist, -cy + dist * 0.001),
        target: ground,
      },
      front: {
        pos: center.clone().add(new THREE.Vector3(0, 0.25 * dist, dist)),
        target: center.clone(),
      },
      side: {
        pos: center.clone().add(new THREE.Vector3(dist, 0.25 * dist, 0)),
        target: center.clone(),
      },
    };

    camera.position.copy(viewsRef.current.iso.pos);

    // --- Controles ---
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.maxPolarAngle = Math.PI / 2 - 0.02;
    controls.minDistance = size * 0.08;
    controls.maxDistance = size * 8;
    controls.autoRotateSpeed = 1.2;
    controls.target.copy(viewsRef.current.iso.target);
    controls.update();
    controlsRef.current = controls;

    const onControlsStart = () => {
      animRef.current = null;
    };
    controls.addEventListener('start', onControlsStart);

    // --- Resaltado (hover / selección) ---
    let hoveredMesh = null;

    const refreshHighlight = () => {
      meshes.forEach((m) => {
        const sel = m.userData.id === selectedIdRef.current;
        const hov = m === hoveredMesh;
        const color = sel ? COLOR_SELECTED : COLOR_HOVER;
        const intensity = sel ? 0.55 : hov ? 0.35 : 0;

        [m.userData.matSolid, m.userData.matHeight].forEach((mat) => {
          mat.emissive.setHex(color);
          mat.emissiveIntensity = intensity;
        });
        m.userData.edge.material.color.setHex(sel ? COLOR_SELECTED : COLOR_EDGE);
        m.userData.edge.material.opacity = sel ? 1 : 0.6;
      });
    };
    refreshHighlightRef.current = refreshHighlight;

    focusRegionRef.current = (id) => {
      const mesh = meshes.find((m) => m.userData.id === id);
      if (!mesh) return;
      const box = new THREE.Box3().setFromObject(mesh);
      const c = box.getCenter(new THREE.Vector3());
      const s = box.getSize(new THREE.Vector3());
      const d = Math.max(s.x, s.z, 4) * 1.6 + s.y;
      const dir = new THREE.Vector3(0.7, 0.65, 0.7).normalize();
      flyTo(c.clone().add(dir.multiplyScalar(d)), c);
    };

    // --- Picking ---
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();

    const pick = (evt) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((evt.clientX - rect.left) / rect.width) * 2 - 1,
        -((evt.clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(meshes, false);
      return hits.length ? hits[0] : null;
    };

    let moveRaf = 0;
    let lastEvt = null;
    let downInfo = null;

    const onPointerMove = (evt) => {
      if (evt.pointerType === 'touch' || evt.buttons !== 0) {
        if (hoveredMesh) {
          hoveredMesh = null;
          refreshHighlight();
        }
        setTooltip((prev) => (prev ? null : prev));
        return;
      }

      lastEvt = evt;
      if (moveRaf) return;

      moveRaf = requestAnimationFrame(() => {
        moveRaf = 0;
        if (!lastEvt) return;

        const hit = pick(lastEvt);
        const mesh = hit ? hit.object : null;

        if (mesh !== hoveredMesh) {
          hoveredMesh = mesh;
          refreshHighlight();
        }

        if (hit) {
          const rect = el.getBoundingClientRect();
          setTooltip({
            x: Math.min(lastEvt.clientX - rect.left + 14, rect.width - 210),
            y: Math.min(lastEvt.clientY - rect.top + 14, rect.height - 64),
            id: mesh.userData.id,
            z: hit.point.y,
          });
        } else {
          setTooltip((prev) => (prev ? null : prev));
        }
      });
    };

    const onPointerLeave = () => {
      lastEvt = null;
      if (hoveredMesh) {
        hoveredMesh = null;
        refreshHighlight();
      }
      setTooltip(null);
    };

    const onPointerDown = (evt) => {
      downInfo = { x: evt.clientX, y: evt.clientY, button: evt.button };
      setTooltip(null);
    };

    const onPointerUp = (evt) => {
      if (!downInfo || downInfo.button !== 0) return;
      const moved = Math.hypot(evt.clientX - downInfo.x, evt.clientY - downInfo.y);
      downInfo = null;
      if (moved > 5) return; // fue un arrastre, no un clic

      const hit = pick(evt);
      setSelectedId(hit ? hit.object.userData.id : null);
    };

    const onDoubleClick = (evt) => {
      const hit = pick(evt);
      if (!hit) return;
      const id = hit.object.userData.id;
      setSelectedId(id);
      if (focusRegionRef.current) focusRegionRef.current(id);
    };

    const dom = renderer.domElement;
    dom.addEventListener('pointermove', onPointerMove);
    dom.addEventListener('pointerleave', onPointerLeave);
    dom.addEventListener('pointerdown', onPointerDown);
    dom.addEventListener('pointerup', onPointerUp);
    dom.addEventListener('dblclick', onDoubleClick);

    // --- Loop ---
    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);

      const anim = animRef.current;
      if (anim) {
        const k = Math.min((performance.now() - anim.t0) / anim.duration, 1);
        const e = 1 - Math.pow(1 - k, 3);
        camera.position.lerpVectors(anim.fromPos, anim.toPos, e);
        controls.target.lerpVectors(anim.fromTarget, anim.toTarget, e);
        if (k >= 1) animRef.current = null;
      }

      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // --- Resize (también cubre pantalla completa) ---
    const ro = new ResizeObserver(() => {
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(el);

    setSceneVersion((v) => v + 1);

    return () => {
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      groupsRef.current = null;
      viewsRef.current = null;
      animRef.current = null;
      refreshHighlightRef.current = null;
      focusRegionRef.current = null;

      cancelAnimationFrame(raf);
      cancelAnimationFrame(moveRaf);
      ro.disconnect();

      dom.removeEventListener('pointermove', onPointerMove);
      dom.removeEventListener('pointerleave', onPointerLeave);
      dom.removeEventListener('pointerdown', onPointerDown);
      dom.removeEventListener('pointerup', onPointerUp);
      dom.removeEventListener('dblclick', onDoubleClick);
      controls.removeEventListener('start', onControlsStart);
      controls.dispose();

      meshes.forEach((m) => {
        m.userData.matSolid.dispose();
        m.userData.matHeight.dispose();
      });
      disposeObject(roofGroup);
      disposeObject(labelsGroup);
      disposeObject(grid);

      renderer.dispose();
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, [model3dData, flyTo]);

  // ----------------------------------------------------------
  // OPCIONES DE VISUALIZACIÓN (sin reconstruir la escena)
  // ----------------------------------------------------------

  useEffect(() => {
    const g = groupsRef.current;
    if (!g) return;

    g.labels.visible = showLabels;
    g.grid.visible = showGrid;

    g.meshes.forEach((m) => {
      const { matSolid, matHeight, edge } = m.userData;
      m.material = colorMode === 'altura' ? matHeight : matSolid;
      [matSolid, matHeight].forEach((mat) => {
        mat.opacity = opacity;
        mat.depthWrite = opacity > 0.9;
      });
      edge.visible = showEdges;
    });

    if (controlsRef.current) controlsRef.current.autoRotate = autoRotate;
  }, [sceneVersion, showLabels, showGrid, showEdges, colorMode, opacity, autoRotate]);

  // Selección -> resaltado
  useEffect(() => {
    selectedIdRef.current = selectedId;
    if (refreshHighlightRef.current) refreshHighlightRef.current();
  }, [selectedId, sceneVersion]);

  // ----------------------------------------------------------
  // MÁSTILES
  // ----------------------------------------------------------

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return undefined;

    const mastGroup = new THREE.Group();
    mastGroup.name = 'masts';
    mastGroup.visible = showMasts;

    masts.forEach((mast) => {
      const mx = mast.posicion_x || 0;
      const my = mast.posicion_y || 0;
      const mz = mast.posicion_z || 0;
      const alturaTotal = mast.altura || 1;
      const alturaCono = Math.min(0.3, alturaTotal * 0.25);
      const alturaCilindro = alturaTotal - alturaCono;
      const color = getMastColor(alturaTotal);

      const group = new THREE.Group();
      group.position.set(mx, mz, -my);

      const poleMesh = new THREE.Mesh(
        new THREE.CylinderGeometry(0.08, 0.12, alturaCilindro, 16),
        new THREE.MeshStandardMaterial({ color, metalness: 0.8, roughness: 0.2 })
      );
      poleMesh.position.set(0, alturaCilindro / 2, 0);
      group.add(poleMesh);

      const tipMesh = new THREE.Mesh(
        new THREE.ConeGeometry(0.14, alturaCono, 16),
        new THREE.MeshStandardMaterial({ color, emissive: color, emissiveIntensity: 0.35 })
      );
      tipMesh.position.set(0, alturaCilindro + alturaCono / 2, 0);
      group.add(tipMesh);

      mastGroup.add(group);
    });

    scene.add(mastGroup);

    return () => {
      scene.remove(mastGroup);
      disposeObject(mastGroup);
    };
  }, [sceneVersion, masts, showMasts]);

  // ----------------------------------------------------------
  // COBERTURA SPDA
  // ----------------------------------------------------------

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !coverageData) return undefined;

    const group = buildCoberturaGroup(coverageData, {
      superficies: showSuperficies,
      zonas: showZonas,
    });
    scene.add(group);

    return () => {
      scene.remove(group);
      disposeGroup(group);
    };
  }, [sceneVersion, coverageData, showSuperficies, showZonas]);

  // ----------------------------------------------------------
  // RENDER
  // ----------------------------------------------------------

  const tooltipRegion = tooltip ? regionList.find((r) => r.id === tooltip.id) : null;
  const noGeometry = !loading && !error && model3dData && regionList.length === 0;

  return (
    <div
      ref={containerRef}
      className="flex flex-col h-full w-full bg-slate-900 rounded-md overflow-hidden border border-slate-700 relative shadow-inner"
    >
      {/* Barra superior: vistas y acciones */}
      <div className="bg-slate-800 border-b border-slate-700 px-3 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 z-10">
        <div className="flex items-center gap-2 text-white font-condensed font-bold text-xs">
          <Box className="w-4 h-4 text-brand-blue" />
          <span>Visor 3D</span>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-slate-400 mr-1">Vista:</span>
          <ToolBtn onClick={() => setView('iso')} title="Vista isométrica">Isométrica</ToolBtn>
          <ToolBtn onClick={() => setView('top')} title="Vista desde arriba">Planta</ToolBtn>
          <ToolBtn onClick={() => setView('front')} title="Vista frontal">Frontal</ToolBtn>
          <ToolBtn onClick={() => setView('side')} title="Vista lateral">Lateral</ToolBtn>
          <span className="w-px h-5 bg-slate-600 mx-1" />
          <ToolBtn onClick={handleReset} title="Volver a la vista inicial">
            <RefreshCw className="w-3 h-3" /> Restablecer
          </ToolBtn>
          <ToolBtn
            onClick={toggleFullscreen}
            title={isFullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}
          >
            {isFullscreen ? <Minimize2 className="w-3 h-3" /> : <Maximize2 className="w-3 h-3" />}
          </ToolBtn>
        </div>
      </div>

      {/* Barra de opciones */}
      <div className="bg-slate-800/80 border-b border-slate-700 px-3 py-1.5 flex flex-wrap items-center gap-x-4 gap-y-1.5 z-10">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-slate-400">Color:</span>
          <Chip active={colorMode === 'altura'} onClick={() => setColorMode('altura')} title="Colorear según la altura">
            Por altura
          </Chip>
          <Chip active={colorMode === 'unico'} onClick={() => setColorMode('unico')} title="Un solo color">
            Único
          </Chip>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-slate-400">Mostrar:</span>
          <Chip active={showLabels} onClick={() => setShowLabels((v) => !v)} title="Cotas de nivel">Cotas</Chip>
          <Chip active={showEdges} onClick={() => setShowEdges((v) => !v)} title="Bordes de las cubiertas">Bordes</Chip>
          <Chip active={showGrid} onClick={() => setShowGrid((v) => !v)} title="Grilla del piso">Grilla</Chip>
          {masts.length > 0 && (
            <Chip active={showMasts} onClick={() => setShowMasts((v) => !v)} title="Mástiles">Mástiles</Chip>
          )}
          {coverageData && (
            <>
              <Chip active={showSuperficies} onClick={() => setShowSuperficies((v) => !v)} title="Esferas de cobertura">
                <span className="inline-block w-2 h-2 rounded-full bg-cyan-400 mr-1" />Esferas
              </Chip>
              <Chip active={showZonas} onClick={() => setShowZonas((v) => !v)} title="Zonas a corregir">
                <span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1" />Zonas a corregir
              </Chip>
            </>
          )}
        </div>

        <label className="flex items-center gap-1.5 text-[11px] text-slate-400">
          Opacidad
          <input
            type="range"
            min="0.2"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
            className="w-20 accent-sky-400"
            aria-label="Opacidad de las cubiertas"
          />
        </label>

        <Chip active={autoRotate} onClick={() => setAutoRotate((v) => !v)} title="Girar el modelo automáticamente">
          <RotateCw className="w-3 h-3 inline -mt-0.5 mr-1" />Girar
        </Chip>
      </div>

      {/* Zona 3D */}
      <div className="flex-1 w-full min-h-[300px] relative">
        <div
          ref={mountRef}
          className="absolute inset-0"
          style={{ cursor: tooltip ? 'pointer' : 'grab' }}
        />

        {/* Estados: cargando / error / vacío */}
        {loading && (
          <div className="absolute inset-0 bg-slate-900 flex flex-col items-center justify-center text-slate-300 z-20">
            <Loader2 className="w-8 h-8 text-brand-blue animate-spin mb-2" />
            <span className="text-xs font-semibold">Cargando modelo 3D...</span>
          </div>
        )}

        {!loading && error && (
          <div className="absolute inset-0 bg-slate-900/95 flex flex-col items-center justify-center text-center px-6 z-20">
            <AlertTriangle className="w-8 h-8 text-amber-400 mb-2" />
            <p className="text-xs text-slate-200 mb-3 max-w-xs">{error}</p>
            <ToolBtn onClick={fetchModel} title="Reintentar">
              <RefreshCw className="w-3 h-3" /> Reintentar
            </ToolBtn>
          </div>
        )}

        {noGeometry && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-6 z-10 pointer-events-none">
            <Box className="w-8 h-8 text-slate-500 mb-2" />
            <p className="text-xs text-slate-300 max-w-xs">
              El modelo no tiene cubiertas para mostrar. Vuelva al paso anterior y verifique que el plano tenga polígonos de techo (ROOF).
            </p>
          </div>
        )}

        {/* Panel de cubiertas */}
        {regionList.length > 0 && (
          <div className="absolute top-2 left-2 z-10 w-52 max-h-[60%] flex flex-col bg-slate-800/95 border border-slate-700 rounded-md shadow-lg">
            <button
              type="button"
              onClick={() => setPanelOpen((v) => !v)}
              className="flex items-center justify-between px-2.5 py-1.5 text-[11px] font-bold text-slate-200 hover:text-white"
              aria-expanded={panelOpen}
            >
              <span>Cubiertas ({regionList.length})</span>
              {panelOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {panelOpen && (
              <ul className="overflow-y-auto border-t border-slate-700">
                {regionList.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedId(r.id);
                        if (focusRegionRef.current) focusRegionRef.current(r.id);
                      }}
                      className={`w-full flex items-center justify-between gap-2 px-2.5 py-1.5 text-left text-[11px] transition ${r.id === selectedId
                          ? 'bg-amber-500/20 text-amber-200'
                          : 'text-slate-300 hover:bg-slate-700'
                        }`}
                    >
                      <span className="flex items-center gap-1 truncate">
                        {r.sinNiveles && (
                          <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" aria-label="Sin niveles" />
                        )}
                        <span className="truncate">{r.id}</span>
                      </span>
                      <span className="text-slate-400 shrink-0">
                        {r.zlow === r.zhigh ? `${fmt(r.zhigh)} m` : `${fmt(r.zlow)}–${fmt(r.zhigh)} m`}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Detalle de la cubierta seleccionada */}
        {selected && (
          <div className="absolute top-2 right-2 z-10 w-60 bg-slate-800/95 border border-amber-500/60 rounded-md shadow-lg text-[11px] text-slate-200">
            <div className="flex items-center justify-between px-2.5 py-1.5 border-b border-slate-700">
              <span className="font-bold truncate">{selected.id}</span>
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                className="text-slate-400 hover:text-white"
                aria-label="Cerrar detalle"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <dl className="px-2.5 py-2 space-y-1">
              <div className="flex justify-between gap-2">
                <dt className="text-slate-400">Tipo</dt>
                <dd className="text-right">{tipoLabel(selected.tipo)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-400">Altura baja</dt>
                <dd>{fmt(selected.zlow)} m</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-400">Altura alta</dt>
                <dd>{fmt(selected.zhigh)} m</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-400">Desnivel</dt>
                <dd>{selected.plana ? 'Plana (0.00 m)' : `${fmt(selected.desnivel)} m`}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-400">Área</dt>
                <dd>{fmt(selected.area, 1)} m²</dd>
              </div>
            </dl>

            {selected.sinNiveles && (
              <p className="px-2.5 pb-2 text-amber-300 flex gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
                Esta cubierta no tiene niveles asociados; la altura es una estimación. Asócielos en el paso de validación.
              </p>
            )}

            {selected.niveles.length > 0 && (
              <div className="px-2.5 pb-2">
                <p className="text-slate-400 mb-1">Niveles asociados</p>
                <ul className="space-y-0.5 max-h-24 overflow-y-auto">
                  {selected.niveles.map((n, i) => {
                    const v = num(n.valor ?? n.value);
                    return (
                      <li key={n.id || i} className="flex justify-between">
                        <span>{v === null ? '—' : formatLevel(v)} m</span>
                        <span className="text-slate-400">
                          {Number.isInteger(n.lado) ? `lado ${n.lado}` : ''}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            <div className="px-2.5 pb-2">
              <ToolBtn
                onClick={() => focusRegionRef.current && focusRegionRef.current(selected.id)}
                title="Acercar la cámara a esta cubierta"
              >
                <Crosshair className="w-3 h-3" /> Enfocar
              </ToolBtn>
            </div>
          </div>
        )}

        {/* Leyenda de alturas */}
        {colorMode === 'altura' && regionList.length > 0 && !selected && (
          <div className="absolute top-2 right-2 z-10 flex items-stretch gap-1.5 bg-slate-800/90 border border-slate-700 rounded-md px-2 py-1.5 text-[10px] text-slate-300 pointer-events-none">
            <div className="w-2.5 h-24 rounded-sm" style={{ background: LEGEND_GRADIENT }} />
            <div className="flex flex-col justify-between">
              <span>{fmt(heightRange.zMax)} m</span>
              <span>{fmt(heightRange.zMin)} m</span>
            </div>
          </div>
        )}

        {/* Tooltip al pasar el mouse */}
        {tooltip && (
          <div
            className="absolute z-20 pointer-events-none bg-slate-900/95 border border-slate-600 rounded px-2 py-1.5 text-[11px] text-slate-100 shadow-lg"
            style={{ left: tooltip.x, top: tooltip.y, maxWidth: 200 }}
          >
            <div className="font-bold truncate">{tooltip.id}</div>
            <div className="text-slate-300">Altura en el cursor: {fmt(tooltip.z)} m</div>
            {tooltipRegion && (
              <div className="text-slate-400 truncate">{tipoLabel(tooltipRegion.tipo)}</div>
            )}
          </div>
        )}

        {/* Ayuda de controles */}
        {showHint && model3dData && !loading && !error && (
          <div className="absolute bottom-2 left-2 z-10 flex items-start gap-2 bg-slate-800/90 border border-slate-700 rounded-md px-2.5 py-1.5 text-[10px] text-slate-300 max-w-[85%]">
            <p>
              <strong className="text-slate-100">Arrastrar</strong> rota ·{' '}
              <strong className="text-slate-100">Clic derecho</strong> mueve ·{' '}
              <strong className="text-slate-100">Rueda</strong> acerca ·{' '}
              <strong className="text-slate-100">Clic</strong> selecciona una cubierta ·{' '}
              <strong className="text-slate-100">Doble clic</strong> la enfoca
            </p>
            <button
              type="button"
              onClick={() => setShowHint(false)}
              className="text-slate-400 hover:text-white shrink-0"
              aria-label="Ocultar ayuda"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Modelo3DViewer;