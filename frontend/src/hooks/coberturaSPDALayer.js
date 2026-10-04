import * as THREE from 'three';

/**
 * Capa 3D de cobertura SPDA (esfera rodante por ternas de mástiles).
 *
 * Convención FARADYNE: el backend envía [x, y, z] con Z = altura.
 * Three.js usa Y como altura, y el visor dibuja (x, z, -y).
 *
 * Se dibuja la mitad inferior de cada esfera y las zonas desprotegidas.
 * Las ternas sin esfera posible NO se dibujan.
 */

const COLORS = {
  superficie: 0x009933, // hemisferio inferior
  malla: 0xa5f3fc,      // aristas de la malla
  zona: 0xef4444,       // zona desprotegida
  zonaBorde: 0xfca5a5,
};

// Orden de dibujo fijo: evita el parpadeo de colores al mover la cámara.
const ORDER = { superficie: 10, zona: 11 };

const toV3 = (p, lift = 0) => new THREE.Vector3(p[0], p[2] + lift, -p[1]);
const toArr = (m) => (Array.isArray(m) ? m : [m]);

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

/** Geometría del hemisferio inferior: del backend, o local si no vino malla. */
function geometriaHemisferio(sup) {
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
  const geo = geometriaHemisferio(sup);
  if (!geo) return null;

  // Asegura normales suaves para que la esfera se vea continua.
  geo.computeVertexNormals();

  const material = new THREE.MeshStandardMaterial({
    color: COLORS.superficie,
    transparent: true,
    opacity: 0.30,

    // Importante: sin wireframe
    wireframe: false,

    // Superficie visible desde ambos lados
    side: THREE.DoubleSide,

    // Transparencia
    depthWrite: false,

    roughness: 0.4,
    metalness: 0.0,
  });

  const mesh = new THREE.Mesh(geo, material);

  mesh.name = `superficie_${sup.id}`;
  mesh.renderOrder = ORDER.superficie;

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