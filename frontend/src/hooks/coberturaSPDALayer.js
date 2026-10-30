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
 * Cada superficie se dibuja como MALLA DE TRIÁNGULOS (líneas) más un relleno muy
 * tenue. Cuanto más densa es la malla, más "sólida" se ve la superficie; cuanto
 * más separados están los triángulos, más transparente se ve (ver DENSIDAD más abajo).
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

// ──────────────────────────────────────────────────────────────────────────────
// AJUSTES DE LA MALLA  ← acá se cambia la densidad y el aspecto
// ──────────────────────────────────────────────────────────────────────────────

/** Color de las líneas de la malla (celeste claro, como en la referencia). */
const COLOR_MALLA = 0x9be7ff;

/**
 * DENSIDAD DE TRIÁNGULOS.
 * Cada nivel parte cada triángulo en 4 (×4 triángulos):
 *   0 = la malla tal cual la manda el backend
 *   1 = 4 veces más triángulos   2 = 16 veces   3 = 64 veces
 * Subilo para una malla más densa (superficie más "sólida"); bajalo para
 * una más abierta (más transparente).
 */
const SUBDIVISION = 0;

/** Tope de triángulos por superficie: corta la subdivisión si se pasa (rendimiento). */
const MAX_TRIANGULOS_POR_SUPERFICIE = 2000;

/**
 * OPACIDAD SEGÚN DENSIDAD.
 * La opacidad del relleno se calcula con los triángulos por m² de cada superficie:
 *   densidad baja  → relleno cerca de `min`  (se ve transparente)
 *   densidad alta  → relleno cerca de `max`  (se ve más sólida)
 * `DENSIDAD_SATURACION` es la densidad (triángulos/m²) a partir de la cual el
 * relleno ya llega al máximo. Más chico = se vuelve sólida con menos triángulos.
 */
const OPACIDAD_RELLENO = { min: 0.04, max: 0.45 };
const DENSIDAD_SATURACION = 0.8; // triángulos por m²

/** Opacidad de las líneas de la malla (0–1). */
const OPACIDAD_LINEAS = 0.5;

// Orden de dibujo fijo: evita el parpadeo de colores al mover la cámara.
const ORDER = { superficie: 10, malla: 10.5, zona: 11, fallo: 12 };

const toV3 = (p, lift = 0) => new THREE.Vector3(p[0], p[2] + lift, -p[1]);
const toArr = (m) => (Array.isArray(m) ? m : [m]);
const clamp01 = (x) => Math.min(1, Math.max(0, x));

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

/**
 * Subdivide cada triángulo en 4 usando los puntos medios de sus aristas
 * (los puntos medios se comparten entre triángulos vecinos, sin duplicar).
 * Devuelve { vertices, triangulos } con el mismo formato que el backend.
 */
function subdividir(vertices, triangulos, niveles) {
  let verts = vertices.map((p) => [p[0], p[1], p[2]]);
  let tris = triangulos.map((t) => [t[0], t[1], t[2]]);

  for (let n = 0; n < niveles; n += 1) {
    if (tris.length * 4 > MAX_TRIANGULOS_POR_SUPERFICIE) break;
    const medios = new Map();
    const medio = (a, b) => {
      const clave = a < b ? `${a}_${b}` : `${b}_${a}`;
      let idx = medios.get(clave);
      if (idx === undefined) {
        const pa = verts[a];
        const pb = verts[b];
        idx = verts.length;
        verts.push([(pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, (pa[2] + pb[2]) / 2]);
        medios.set(clave, idx);
      }
      return idx;
    };
    const nuevos = [];
    tris.forEach(([a, b, c]) => {
      const ab = medio(a, b);
      const bc = medio(b, c);
      const ca = medio(c, a);
      nuevos.push([a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]);
    });
    tris = nuevos;
  }
  return { vertices: verts, triangulos: tris };
}

/** Área total (m²) de la malla; sirve para calcular la densidad de triángulos. */
function areaMalla(vertices, triangulos) {
  const a = new THREE.Vector3();
  const b = new THREE.Vector3();
  const c = new THREE.Vector3();
  let total = 0;
  triangulos.forEach(([i, j, k]) => {
    a.set(...vertices[i]);
    b.set(...vertices[j]);
    c.set(...vertices[k]);
    total += b.sub(a).cross(c.sub(a)).length() / 2;
  });
  return total;
}

/** Opacidad del relleno según los triángulos por m² (ver OPACIDAD_RELLENO). */
function opacidadPorDensidad(nTriangulos, area) {
  if (!(area > 0)) return OPACIDAD_RELLENO.min;
  const densidad = nTriangulos / area; // triángulos por m²
  const t = clamp01(densidad / DENSIDAD_SATURACION);
  return OPACIDAD_RELLENO.min + (OPACIDAD_RELLENO.max - OPACIDAD_RELLENO.min) * t;
}

/** Geometría de la superficie a partir de la malla del backend. */
function geometriaSuperficie(sup) {
  if (!sup.vertices?.length || !sup.triangulos?.length) return null;

  const malla = SUBDIVISION > 0
    ? subdividir(sup.vertices, sup.triangulos, SUBDIVISION)
    : { vertices: sup.vertices, triangulos: sup.triangulos };

  const pos = new Float32Array(malla.vertices.length * 3);
  malla.vertices.forEach((p, i) => {
    pos[3 * i] = p[0];
    pos[3 * i + 1] = p[2];
    pos[3 * i + 2] = -p[1];
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setIndex(malla.triangulos.flat());
  geo.computeVertexNormals();
  geo.userData.opacidadRelleno = opacidadPorDensidad(
    malla.triangulos.length,
    areaMalla(malla.vertices, malla.triangulos),
  );
  return geo;
}

function buildSuperficie(sup, { malla = true } = {}) {
  const geo = geometriaSuperficie(sup);
  if (!geo) return null;

  // Relleno: más tenue cuanto más abierta es la malla, más sólido cuanto más densa.
  const material = new THREE.MeshStandardMaterial({
    color: colorSuperficie(sup.tipo),
    transparent: true,
    opacity: malla ? geo.userData.opacidadRelleno : 0.6,
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

  if (malla) {
    // WireframeGeometry deduplica las aristas compartidas entre triángulos.
    const lineas = new THREE.LineSegments(
      new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({
        color: COLOR_MALLA,
        transparent: true,
        opacity: OPACIDAD_LINEAS,
        depthWrite: false,
      }),
    );
    lineas.name = `malla_${sup.id}`;
    lineas.renderOrder = ORDER.malla;
    lineas.userData = { id: sup.id, tipo: sup.tipo };
    g.add(lineas);
  }
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

/**
 * Construye el grupo three con la cobertura (respuesta de /cobertura/proyecto/{id}).
 * `malla: false` vuelve al aspecto de superficie sólida, sin líneas.
 */
export function buildCoberturaGroup(coverage, { superficies = true, zonas = true, malla = true } = {}) {
  const root = new THREE.Group();
  root.name = 'cobertura_spda';
  if (!coverage) return root;

  if (superficies) {
    (coverage.superficies_esfera || []).forEach((s) => {
      const g = buildSuperficie(s, { malla });
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