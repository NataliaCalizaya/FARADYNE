import * as THREE from 'three';

/**
 * Capa 3D de cobertura SPDA (esfera rodante por ternas de mástiles).
 *
 * Convención FARADYNE: el backend envía [x, y, z] con Z = altura.
 * Three.js usa Y como altura, y el visor dibuja (x, z, -y), igual que
 * addPrismToScene y los mástiles en Modelo3DViewer.
 */

const COLORS = {
  superficie: 0x22d3ee, // casquetes de esfera
  malla: 0xa5f3fc,      // aristas de la malla
  zona: 0xef4444,       // zona desprotegida
  zonaBorde: 0xfca5a5,
  terna: 0xf59e0b,      // terna sin esfera posible
};

const toV3 = (p, lift = 0) => new THREE.Vector3(p[0], p[2] + lift, -p[1]);

const toArr = (m) => (Array.isArray(m) ? m : [m]);

function overlayMaterial(color, opacity) {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity,
    side: THREE.DoubleSide,
    depthWrite: false,
    polygonOffset: true,       // evita z-fighting con la cubierta
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  });
}

function buildSuperficie(sup) {
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

  const g = new THREE.Group();
  g.name = `superficie_${sup.id}`;
  g.add(
    new THREE.Mesh(
      geo,
      new THREE.MeshStandardMaterial({
        color: COLORS.superficie,
        transparent: true,
        opacity: 0.28,
        side: THREE.DoubleSide,
        depthWrite: false,
        roughness: 0.4,
      })
    )
  );
  g.add(
    new THREE.LineSegments(
      new THREE.WireframeGeometry(geo),
      new THREE.LineBasicMaterial({ color: COLORS.malla, transparent: true, opacity: 0.55 })
    )
  );
  return g;
}

function buildZona(zona, lift = 0.03) {
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
    pos[3 * i + 1] = p[2] + lift;
    pos[3 * i + 2] = -p[1];
  });

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setIndex(tris.flat());

  const g = new THREE.Group();
  g.name = `zona_${zona.id}`;
  g.add(new THREE.Mesh(geo, overlayMaterial(COLORS.zona, 0.55)));
  g.add(
    new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(contorno.map((p) => toV3(p, lift))),
      new THREE.LineBasicMaterial({ color: COLORS.zonaBorde })
    )
  );
  return g;
}

function buildTerna(terna) {
  if ((terna.puntas || []).length !== 3) return null;
  const pts = terna.puntas.map((p) => toV3(p, 0.02));

  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  geo.setIndex([0, 1, 2]);

  const g = new THREE.Group();
  g.name = `terna_sin_esfera_${terna.id}`;
  g.add(new THREE.Mesh(geo, overlayMaterial(COLORS.terna, 0.3)));
  g.add(
    new THREE.LineLoop(
      new THREE.BufferGeometry().setFromPoints(pts),
      new THREE.LineBasicMaterial({ color: COLORS.terna })
    )
  );
  return g;
}

/** Construye el grupo three con toda la cobertura (respuesta de /cobertura/proyecto/{id}). */
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
    (coverage.triangulos_sin_esfera || []).forEach((t) => {
      const g = buildTerna(t);
      if (g) root.add(g);
    });
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
