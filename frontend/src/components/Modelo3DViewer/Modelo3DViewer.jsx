import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three-stdlib';
import { RefreshCw, Box, Eye, Loader2 } from 'lucide-react';
import { modelos3dApi } from '../../api/modelos3d';

/**
 * FARADYNE Model Convention:
 * Model X = plant width
 * Model Y = plant depth
 * Model Z = real height (elevation)
 *
 * Three.js uses Y as vertical axis:
 * Three X = Model X
 * Three Y = Model Z
 * Three Z = Model Y
 */

function roofHeight(region, x, y) {
  const pair = region.slope_pair ?? [];
  if (pair.length === 2) {
    const a = pair[0], b = pair[1];
    const dx = b.x - a.x, dy = b.y - a.y;
    const den = dx * dx + dy * dy;
    if (den > 1e-9) {
      const dz = b.value - a.value;
      const A = (dz * dx) / den;
      const B = (dz * dy) / den;
      const C = a.value - A * a.x - B * a.y;
      return Math.max(0, A * x + B * y + C);
    }
  }
  const levels = region.levels || [];
  return Math.max(...(levels.length ? levels : [3.7]));
}

function addRegionToScene(scene, region) {
  const fp = region.footprint || region.points || [];
  const pts = fp.map(([x, y]) => new THREE.Vector2(x, y));
  if (pts.length < 3) return;

  const tri = THREE.ShapeUtils.triangulateShape(pts, []);
  const zTop = pts.map((p) => roofHeight(region, p.x, p.y));
  const positions = [];

  // Top sloped roof & bottom base faces (Model X,Y,Z -> Three X,Z,Y)
  for (const t of tri) {
    const a = t[0], b = t[1], c = t[2];

    positions.push(
      pts[a].x, zTop[a], pts[a].y,
      pts[b].x, zTop[b], pts[b].y,
      pts[c].x, zTop[c], pts[c].y
    );

    positions.push(
      pts[c].x, 0, pts[c].y,
      pts[b].x, 0, pts[b].y,
      pts[a].x, 0, pts[a].y
    );
  }

  // Side walls
  for (let i = 0; i < pts.length; i++) {
    const j = (i + 1) % pts.length;
    const a = pts[i], b = pts[j];
    positions.push(
      a.x, 0, a.y,
      b.x, 0, b.y,
      b.x, zTop[j], b.y
    );
    positions.push(
      a.x, 0, a.y,
      b.x, zTop[j], b.y,
      a.x, zTop[i], a.y
    );
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();

  const material = new THREE.MeshStandardMaterial({
    transparent: true,
    opacity: 0.72,
    color: new THREE.Color(0x38bdf8),
    side: THREE.DoubleSide,
    roughness: 0.65,
    metalness: 0.1,
  });
  const mesh = new THREE.Mesh(geo, material);
  mesh.name = region.id || 'roof_region';
  scene.add(mesh);

  const edge = new THREE.LineSegments(
    new THREE.EdgesGeometry(geo),
    new THREE.LineBasicMaterial({ color: 0x0284c7, transparent: true, opacity: 0.6 })
  );
  scene.add(edge);
}

function addLabelToScene(scene, x, y, z, text) {
  const cv = document.createElement('canvas');
  cv.width = 180;
  cv.height = 54;
  const ctx = cv.getContext('2d');
  if (!ctx) return;
  ctx.fillStyle = 'rgba(255,255,255,.92)';
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = '#0f172a';
  ctx.font = 'bold 26px Arial';
  ctx.fillText(text, 10, 36);

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(cv),
      transparent: true,
    })
  );

  sprite.scale.set(2.4, 0.72, 1);
  sprite.position.set(x, z + 0.25, y);
  scene.add(sprite);
}

export const Modelo3DViewer = ({ idModelo2D, idModelo3D, masts = [] }) => {
  const mountRef = useRef(null);
  const controlsRef = useRef(null);
  const cameraRef = useRef(null);
  const targetRef = useRef(new THREE.Vector3(0, 3, 0));
  const initialCamPosRef = useRef(new THREE.Vector3(50, 40, 50));

  const [loading, setLoading] = useState(false);
  const [model3dData, setModel3dData] = useState(null);

  useEffect(() => {
    if (idModelo2D && !idModelo3D) {
      generate3DModel(idModelo2D);
    } else if (idModelo3D) {
      load3DModel(idModelo3D);
    }
  }, [idModelo2D, idModelo3D]);

  const generate3DModel = async (id2d) => {
    setLoading(true);
    try {
      const data = await modelos3dApi.createModelo3D(id2d);
      setModel3dData(data);
    } catch (err) {
      console.error('Error generating 3D model:', err);
    } finally {
      setLoading(false);
    }
  };

  const load3DModel = async (id3d) => {
    setLoading(true);
    try {
      const data = await modelos3dApi.getModelo3D(id3d);
      setModel3dData(data);
    } catch (err) {
      console.error('Error loading 3D model:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);

    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.1, 5000);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x334155, 2.2));
    scene.add(new THREE.DirectionalLight(0xffffff, 1.2));

    const meta = model3dData?.geometria_volumetric || model3dData?.geometria_volumétrica || model3dData || {};
    const regions = meta.regions || meta.poligonos || [];
    regions.forEach((region) => addRegionToScene(scene, region));

    // Render Tank if present
    if (meta.tank) {
      const t = meta.tank;
      const g = new THREE.BoxGeometry(t.width, t.top - t.base, t.depth);
      const m = new THREE.MeshStandardMaterial({
        color: 0xe07a10,
        transparent: true,
        opacity: 0.85,
        roughness: 0.4,
      });
      const mesh = new THREE.Mesh(g, m);
      mesh.position.set(t.x, (t.base + t.top) / 2, t.y);
      scene.add(mesh);
    }

    // Render Level Labels
    const levelMarks = meta.level_marks || meta.cotas_altura || [];
    const seen = new Set();
    for (const mark of levelMarks) {
      const val = mark.value ?? mark.valor ?? 0;
      const x = mark.x ?? (mark.posicion ? mark.posicion[0] : 0);
      const y = mark.y ?? (mark.posicion ? mark.posicion[1] : 0);
      const key = `${val}-${Math.round(x)}-${Math.round(y)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      addLabelToScene(scene, x, y, val, `+${val.toFixed(2)}`);
    }

    // Calculate dynamic camera position & grid bounding box
    const bbox = meta.bbox || [0, 0, 80, 60];
    const [bx0, by0, bx1, by1] = bbox;
    const cx = (bx0 + bx1) / 2;
    const cy = (by0 + by1) / 2;
    const size = Math.max(bx1 - bx0, by1 - by0, 20);

    const gridSize = Math.ceil((size * 1.5) / 5) * 5;
    scene.add(new THREE.GridHelper(gridSize, Math.max(2, Math.ceil(gridSize / 5)), 0x38bdf8, 0x334155));

    initialCamPosRef.current.set(cx + size * 0.95, size * 0.75, cy + size * 0.95);
    targetRef.current.set(cx, 3, cy);

    camera.position.copy(initialCamPosRef.current);
    camera.lookAt(targetRef.current);

    // Render Masts placed in 3D (Three X/Y/Z = Model X/Z/Y)
    masts.forEach((mast, idx) => {
      const mx = mast.posicion_x || 0;
      const my = mast.posicion_y || 0;
      const mz = mast.posicion_z || 4;
      const alt = mast.altura || 3;

      const group = new THREE.Group();
      group.position.set(mx, mz, my);

      const poleGeo = new THREE.CylinderGeometry(0.15, 0.25, alt, 16);
      const poleMat = new THREE.MeshStandardMaterial({ color: 0xe07a10, metalness: 0.8, roughness: 0.2 });
      const poleMesh = new THREE.Mesh(poleGeo, poleMat);
      poleMesh.position.set(0, alt / 2, 0);
      group.add(poleMesh);

      const tipGeo = new THREE.ConeGeometry(0.3, 1, 16);
      const tipMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.5 });
      const tipMesh = new THREE.Mesh(tipGeo, tipMat);
      tipMesh.position.set(0, alt + 0.5, 0);
      group.add(tipMesh);

      scene.add(group);
    });

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.copy(targetRef.current);
    controls.update();
    controlsRef.current = controls;

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!el) return;
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(raf);
      controls.dispose();
      renderer.dispose();
      scene.traverse((obj) => {
        if (obj.geometry) obj.geometry.dispose();
        if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
        else if (obj.material) obj.material.dispose();
      });
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, [model3dData, masts]);

  const handleResetCamera = () => {
    if (controlsRef.current && cameraRef.current) {
      cameraRef.current.position.copy(initialCamPosRef.current);
      controlsRef.current.target.copy(targetRef.current);
      controlsRef.current.update();
    }
  };

  return (
    <div className="flex flex-col h-full w-full bg-slate-900 rounded-md overflow-hidden border border-slate-700 relative shadow-inner">
      {/* 3D Viewer Header Toolbar */}
      <div className="bg-slate-800 border-b border-slate-700 px-3 py-2 flex items-center justify-between z-10">
        <div className="flex items-center gap-2 text-white font-condensed font-bold text-xs">
          <Box className="w-4 h-4 text-brand-blue" />
          <span>Visor Tridimensional 3D — Superficies Inclinadas & Tanque</span>
        </div>
        <button
          type="button"
          onClick={handleResetCamera}
          className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 hover:text-white rounded text-[11px] font-semibold flex items-center gap-1.5 transition"
          title="Restablecer vista de cámara inicial"
        >
          <RefreshCw className="w-3 h-3" /> Restablecer vista
        </button>
      </div>

      {/* Canvas 3D viewport */}
      <div className="flex-1 w-full h-[380px] min-h-[300px] relative">
        {loading ? (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-300">
            <Loader2 className="w-8 h-8 text-brand-blue animate-spin mb-2" />
            <span className="text-xs font-semibold">Generando modelo 3D con triangulación de cubiertas...</span>
          </div>
        ) : (
          <div ref={mountRef} className="w-full h-full" />
        )}

        {/* Overlay Instructions */}
        <div className="absolute bottom-3 left-3 bg-slate-800/80 backdrop-blur border border-slate-700 text-slate-300 text-[10px] p-2 rounded flex flex-col gap-1 pointer-events-none">
          <div className="flex items-center gap-1.5 font-semibold text-white">
            <Eye className="w-3 h-3 text-brand-blue" /> Orbit Controls Activos
          </div>
          <div>• Clic izq + arrastrar: Rotar vista 3D</div>
          <div>• Clic der + arrastrar: Desplazar cámara</div>
          <div>• Rueda del mouse: Zoom In/Out</div>
        </div>
      </div>
    </div>
  );
};

export default Modelo3DViewer;
