import * as THREE from 'three';

/**
 * Capa 3D de cobertura SPDA (esfera rodante por ternas de mástiles).
 *
 * Convención FARADYNE: el backend envía [x, y, z] con Z = altura.
 * Three.js usa Y como altura, y el visor dibuja (x, z, -y).
 *
 * Superficies (cada una trae su malla `vertices` + `triangulos`):
 *   parche    triángulo esférico entre 3 puntas
 *   union     banda entre dos ternas que comparten arista
 *   falda     arista exterior prolongada hasta el suelo
 *   casquete  cierre de esquina entre dos faldas
 *
 * Además se dibujan las zonas desprotegidas y las aristas de uniones/faldas
 * que no se pudieron construir (`uniones_sin_superficie`).
 * Las ternas sin esfera (`triangulos_sin_esfera`) NO se dibujan.
 */

const COLORS = {
  parche: 0x009933,
  union: 0x06b6d4,
  falda: 0x3b82f6,
  casquete: 0x8b5cf6,
  zona: 0xef4444,
  zonaBorde: 0xfca5a5,
  fallo: 0xf97316, // arista de unión/falda sin superficie
};

// Orden de dibujo fijo: evita el parpadeo de colores al mover la cámara.
const ORDER = { superficie: 10, zona: 11, fallo: 12 };

const toV3 = (p, lift = 0) => new THREE.Vector3(p[0], p[2] + lift, -p[1]);
const toArr = (m) => (Array.isArray(m) ? m : [m]);

const colorSuperficie = (tipo) => COLORS[tipo] ?? COLORS.parche;

function overlayMaterial(color, opacity) {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    side: THREE.DoubleSide,
    depthWrite: false,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
}

/** Geometría de la superficie a partir de la malla del backend. */
function geometriaSuperficie(sup) {
  if (!sup.vertices?.length || !sup.triangulos?.length) return null;

  const pos = new Float32Array(sup.vertices.length * 3);
  sup.vertices.forEach((p, i) => {
    pos[3 * i] = p[0];
    pos[3 * i + 1] = p[2];
    pos[3 * i + 2] = -p[1];
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setIndex(sup.triangulos.flat());
  geo.computeVertexNormals();
  return geo;
}

function buildSuperficie(sup) {
  const geo = geometriaSuperficie(sup);
  if (!geo) return null;

  const material = new THREE.MeshStandardMaterial({
    color: colorSuperficie(sup.tipo),
    transparent: true,
    opacity: 0.6,
    side: THREE.DoubleSide,
    depthWrite: false,
    roughness: 0.4,
    metalness: 0.0,
  });

  const mesh = new THREE.Mesh(geo, material);
  mesh.name = `superficie_${sup.id}`;
  mesh.renderOrder = ORDER.superficie;
  mesh.userData = { id: sup.id, tipo: sup.tipo };

  const g = new THREE.Group();
  g.name = `superficie_${sup.id}`;
  g.add(mesh);
  return g;
}

function buildZona(zona, lift = 0.08) {
  const contorno = zona.poligono || [];
  const huecos = zona.huecos || [];
  if (contorno.length < 3) return null;

  const v2 = (ps) => ps.map((p) => new THREE.Vector2(p[0], p[1]));
  const tris = THREE.ShapeUtils.triangulateShape(v2(contorno), huecos.map(v2));
  if (!tris.length) return null;

  // Mismo orden que espera triangulateShape: contorno + huecos concatenados.
  const puntos = [contorno, ...huecos].flat();
  const pos = new Float32Array(puntos.length * 3);
  puntos.forEach((p, i) => {
    pos[3 * i] = p[0];
    pos[3 * i + 1] = (p[2] ?? 0) + lift;
    pos[3 * i + 2] = -p[1];
  });

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setIndex(tris.flat());

  const g = new THREE.Group();
  g.name = `zona_${zona.id}`;

  const mesh = new THREE.Mesh(geo, overlayMaterial(COLORS.zona, 0.55));
  mesh.renderOrder = ORDER.zona;
  g.add(mesh);

  const borde = new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(contorno.map((p) => toV3(p, lift))),
    new THREE.LineBasicMaterial({ color: COLORS.zonaBorde, depthWrite: false })
  );
  borde.renderOrder = ORDER.zona + 0.1;
  g.add(borde);
  return g;
}

/** Aristas (entre puntas de mástil) de uniones/faldas que no se pudieron construir. */
function buildFallos(fallos) {
  const pts = [];
  fallos.forEach((f) => {
    const a = f.arista || [];
    if (a.length >= 2) pts.push(toV3(a[0]), toV3(a[1]));
  });
  if (!pts.length) return null;

  const line = new THREE.LineSegments(
    new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color: COLORS.fallo, depthWrite: false, depthTest: false })
  );
  line.name = 'fallos_union_falda';
  line.renderOrder = ORDER.fallo;
  return line;
}

/** Construye el grupo three con la cobertura (respuesta de /cobertura/proyecto/{id}). */
export function buildCoberturaGroup(coverage, { superficies = true, zonas = true } = {}) {
  const root = new THREE.Group();
  root.name = 'cobertura_spda';
  if (!coverage) return root;

  if (superficies) {
    (coverage.superficies_esfera || []).forEach((s) => {
      const g = buildSuperficie(s);
      if (g) root.add(g);
    });
  }
  if (zonas) {
    (coverage.zonas_desprotegidas || []).forEach((z) => {
      const g = buildZona(z);
      if (g) root.add(g);
    });
    const fallos = buildFallos(coverage.uniones_sin_superficie || []);
    if (fallos) root.add(fallos);
    // triangulos_sin_esfera: a propósito no se dibujan.
  }
  return root;
}

/** Libera geometrías y materiales del grupo (llamar al quitarlo de la escena). */
export function disposeGroup(root) {
  root.traverse((o) => {
    o.geometry?.dispose();
    if (o.material) toArr(o.material).forEach((m) => m.dispose());
  });
}