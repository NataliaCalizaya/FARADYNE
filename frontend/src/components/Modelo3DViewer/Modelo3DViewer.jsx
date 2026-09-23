import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three-stdlib';
import { RefreshCw, Box, Eye, Loader2 } from 'lucide-react';
import { modelos3dApi } from '../../api/modelos3d';

/**
 * FARADYNE Model Convention:
 * El Backend Python envía: [x, y, z] donde Z es la altura.
 * Three.js usa Y como altura: X=x, Y=z, Z=y.
 */

function addPrismToScene(scene, prism) {
  if (!prism.faces || prism.faces.length === 0) return;

  const positions = [];

  // El backend envía las caras pre-calculadas (top, bottom, side)
  prism.faces.forEach((face) => {
    const pts = face.points; // Array de [x, y, z] del backend
    if (!pts || pts.length < 3) return;

    // Convertimos la convención de Python a la de Three.js (Y es la altura)
    const v = pts.map(p => new THREE.Vector3(p[0], p[2], -p[1]));

    // Triangulamos caras (Si es un cuadrado/side de 4 puntos, hace 2 triángulos)
    for (let i = 1; i < v.length - 1; i++) {
      positions.push(
        v[0].x, v[0].y, v[0].z,
        v[i].x, v[i].y, v[i].z,
        v[i + 1].x, v[i + 1].y, v[i + 1].z
      );
    }
  });

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
  mesh.name = prism.id || 'roof_region';
  scene.add(mesh);

  // Agregar bordes para mejor visualización
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
      const data = await modelos3dApi.generateModelo3D({ 
        id_modelo2d: id2d 
      });
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
    if (!el || !model3dData) return;

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

    const meta = model3dData.geometria_volumetrica || {};
    
    // AHORA LEE DIRECTAMENTE LOS PRISMAS GENERADOS POR PYTHON
    const prisms = meta.prisms || [];
    prisms.forEach((prism) => addPrismToScene(scene, prism));

    // Render Tanque si existe
    if (meta.tank) {
      const t = meta.tank;
      const g = new THREE.BoxGeometry(t.width, t.top - t.base, t.depth);
      const m = new THREE.MeshStandardMaterial({
        color: 0xe07a10, transparent: true, opacity: 0.85, roughness: 0.4,
      });
      const mesh = new THREE.Mesh(g, m);
      mesh.position.set(t.x, (t.base + t.top) / 2, t.y);
      scene.add(mesh);
    }

    // Render Cotas de Nivel (Labels)
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

    // Cámara y Grilla
    const vista = meta.vista_defecto || model3dData.vista_defecto || {};
    
    if (vista.camera && vista.target) {
        initialCamPosRef.current.set(vista.camera[0], vista.camera[1], vista.camera[2]);
        targetRef.current.set(vista.target[0], vista.target[1], vista.target[2]);
    } else {
        initialCamPosRef.current.set(50, 40, 50);
        targetRef.current.set(0, 3, 0);
    }

    // Dibujar grilla basada en Bounding Box del backend
    const bbox = meta.bbox || [0, 0, 80, 60];
    const size = Math.max(bbox[2] - bbox[0], bbox[3] - bbox[1], 20);
    const gridSize = Math.ceil((size * 1.5) / 5) * 5;
    scene.add(new THREE.GridHelper(gridSize, Math.max(2, Math.ceil(gridSize / 5)), 0x38bdf8, 0x334155));

    camera.position.copy(initialCamPosRef.current);
    camera.lookAt(targetRef.current);

    // Mástiles
    masts.forEach((mast) => {
      const mx = mast.posicion_x || 0;
      const my = mast.posicion_y || 0;
      const mz = mast.posicion_z || 4; // Altura base
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
      <div className="bg-slate-800 border-b border-slate-700 px-3 py-2 flex items-center justify-between z-10">
        <div className="flex items-center gap-2 text-white font-condensed font-bold text-xs">
          <Box className="w-4 h-4 text-brand-blue" />
          <span>Visor 3D (Renderizando geometría del Backend)</span>
        </div>
        <button
          type="button"
          onClick={handleResetCamera}
          className="px-2.5 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 hover:text-white rounded text-[11px] font-semibold flex items-center gap-1.5 transition"
        >
          <RefreshCw className="w-3 h-3" /> Restablecer vista
        </button>
      </div>

      <div className="flex-1 w-full h-[380px] min-h-[300px] relative">
        {loading ? (
          <div className="w-full h-full flex flex-col items-center justify-center text-slate-300">
            <Loader2 className="w-8 h-8 text-brand-blue animate-spin mb-2" />
            <span className="text-xs font-semibold">Cargando Modelo 3D desde el Servidor...</span>
          </div>
        ) : (
          <div ref={mountRef} className="w-full h-full" />
        )}
      </div>
    </div>
  );
};

export default Modelo3DViewer;