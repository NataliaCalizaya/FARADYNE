import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three-stdlib';
import type { Model3DMetadata, Model3DRegion } from '../types';

interface Viewer3DProps { metadata: Model3DMetadata; }

/**
 * Convención del modelo FARADYNE:
 *   X = ancho de la planta
 *   Y = profundidad de la planta
 *   Z = altura real
 *
 * Three.js utiliza Y como eje vertical. Por eso al dibujar hacemos:
 *   Three X = modelo X
 *   Three Y = modelo Z
 *   Three Z = modelo Y
 *
 * Esta conversión es solamente para el visor. El DXF mantiene Z como vertical.
 */
function roofHeight(region: Model3DRegion, x: number, y: number) {
  const pair = region.slope_pair ?? [];
  if (pair.length === 2) {
    const a = pair[0], b = pair[1];
    const dx = b.x - a.x, dy = b.y - a.y;
    const den = dx * dx + dy * dy;
    if (den > 1e-9) {
      const dz = b.value - a.value;
      const A = dz * dx / den;
      const B = dz * dy / den;
      const C = a.value - A * a.x - B * a.y;
      return Math.max(0, A * x + B * y + C);
    }
  }
  return Math.max(...(region.levels.length ? region.levels : [3.7]));
}

function addRegion(scene: THREE.Scene, region: Model3DRegion) {
  const pts = region.footprint.map(([x, y]) => new THREE.Vector2(x, y));
  if (pts.length < 3) return;

  const tri = THREE.ShapeUtils.triangulateShape(pts, []);
  const zTop = pts.map(p => roofHeight(region, p.x, p.y));
  const positions: number[] = [];

  // Techo superior y base.
  for (const t of tri) {
    const a = t[0], b = t[1], c = t[2];

    // modelo (x,y,z) -> Three (x,z,y)
    positions.push(
      pts[a].x, zTop[a], pts[a].y,
      pts[b].x, zTop[b], pts[b].y,
      pts[c].x, zTop[c], pts[c].y,
    );

    positions.push(
      pts[c].x, 0, pts[c].y,
      pts[b].x, 0, pts[b].y,
      pts[a].x, 0, pts[a].y,
    );
  }

  // Paredes laterales.
  for (let i = 0; i < pts.length; i++) {
    const j = (i + 1) % pts.length;
    const a = pts[i], b = pts[j];
    positions.push(
      a.x, 0, a.y,
      b.x, 0, b.y,
      b.x, zTop[j], b.y,
    );
    positions.push(
      a.x, 0, a.y,
      b.x, zTop[j], b.y,
      a.x, zTop[i], a.y,
    );
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geo.computeVertexNormals();

  const material = new THREE.MeshStandardMaterial({
    transparent: true,
    opacity: 0.58,
    side: THREE.DoubleSide,
    roughness: 0.85,
  });
  const mesh = new THREE.Mesh(geo, material);
  mesh.name = region.id;
  scene.add(mesh);

  const edge = new THREE.LineSegments(
    new THREE.EdgesGeometry(geo),
    new THREE.LineBasicMaterial({ transparent: true, opacity: 0.45 }),
  );
  scene.add(edge);
}

function addLabel(scene: THREE.Scene, x: number, y: number, z: number, text: string) {
  const cv = document.createElement('canvas');
  cv.width = 180;
  cv.height = 54;
  const ctx = cv.getContext('2d')!;
  ctx.fillStyle = 'rgba(255,255,255,.92)';
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = '#111';
  ctx.font = 'bold 28px Arial';
  ctx.fillText(text, 10, 37);

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: new THREE.CanvasTexture(cv),
      transparent: true,
    }),
  );

  sprite.scale.set(2.4, 0.72, 1);
  // modelo (x,y,z) -> Three (x,z,y)
  sprite.position.set(x, z + 0.25, y);
  scene.add(sprite);
}

export default function Viewer3D({ metadata }: Viewer3DProps) {
  const mount = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = mount.current;
    if (!el) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f5f7);

    const camera = new THREE.PerspectiveCamera(
      45,
      el.clientWidth / el.clientHeight,
      0.1,
      5000,
    );

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x777777, 2.2));
    scene.add(new THREE.DirectionalLight(0xffffff, 1.1));

    metadata.regions.forEach(region => addRegion(scene, region));

    // Tanque: modelo X/Y/Z -> Three X/Y/Z = X/Z/Y.
    if (metadata.tank) {
      const t = metadata.tank;
      const g = new THREE.BoxGeometry(t.width, t.top - t.base, t.depth);
      const m = new THREE.MeshStandardMaterial({
        transparent: true,
        opacity: 0.72,
      });
      const mesh = new THREE.Mesh(g, m);
      mesh.position.set(t.x, (t.base + t.top) / 2, t.y);
      scene.add(mesh);
    }

    const marks = metadata.regions.flatMap(r => r.level_marks ?? []);
    const seen = new Set<string>();
    for (const m of marks) {
      const key = `${m.value}-${Math.round(m.x)}-${Math.round(m.y)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      addLabel(scene, m.x, m.y, m.value, `+${m.value.toFixed(2)}`);
    }

    const [bx0, by0, bx1, by1] = metadata.bbox;
    const cx = (bx0 + bx1) / 2;
    const cy = (by0 + by1) / 2;
    const size = Math.max(bx1 - bx0, by1 - by0, 20);

    // GridHelper está en XZ y Y es vertical: exactamente la convención de Three.
    const gridSize = Math.ceil(size * 1.25 / 5) * 5;
    scene.add(new THREE.GridHelper(gridSize, Math.max(2, Math.ceil(gridSize / 5))));

    // Vista isométrica: la planta queda horizontal sobre la malla.
    camera.position.set(
      cx + size * 0.95,
      size * 0.75,
      cy + size * 0.95,
    );
    camera.lookAt(cx, 3, cy);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.target.set(cx, 3, cy);
    controls.update();

    let raf = 0;
    const animate = () => {
      raf = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const resize = () => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener('resize', resize);

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(raf);
      controls.dispose();
      renderer.dispose();
      scene.traverse(o => {
        const obj = o as THREE.Mesh;
        if (obj.geometry) obj.geometry.dispose();
        if (Array.isArray(obj.material)) obj.material.forEach(x => x.dispose());
        else if (obj.material) obj.material.dispose();
      });
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, [metadata]);

  return (
    <div
      ref={mount}
      className="viewer3d"
      style={{ width: '100%', height: '100%', minHeight: '520px' }}
    />
  );
}
