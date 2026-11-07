/**
 * vistasTecnicas.js — vistas del modelo 3D para la memoria descriptiva.
 *
 * Además de las vistas "de cámara" del visor (isométrica, frontal, planta y
 * lateral, en perspectiva), define dos proyecciones oblicuas de dibujo técnico.
 * Se obtienen con una cámara ortográfica a la que se le aplica un
 * corte (shear) en el espacio de vista, así que no hace falta otro motor de render:
 *
 *   · Caballera: el frente (alzado) se ve en verdadera magnitud y la
 *     profundidad se dibuja con fugas a 45° y coeficiente de reducción 1.
 *   · Militar (planimétrica): la planta se ve en verdadera magnitud, girada 30°
 *     (ejes a 30° y 60°), y las alturas se dibujan verticales a escala real.
 */
import * as THREE from 'three';

/** Vistas que se pueden capturar (la clave es la que recibe capturarVista). */
export const VISTAS_CAPTURA = [
  { key: 'iso', label: 'Isométrica', detalle: 'Perspectiva en 3D, igual a la del visor' },
  { key: 'iso_der', label: 'Isométrica derecha', detalle: 'Esquina posterior derecha: el lado derecho y el fondo del edificio' },
  { key: 'caballera', label: 'Caballera', detalle: 'Oblicua: frente en verdadera magnitud, fugas a 45°' },
  { key: 'militar', label: 'Militar', detalle: 'Oblicua: planta en verdadera magnitud, alturas verticales' },
  { key: 'front', label: 'Frontal', detalle: 'Vista desde el frente' },
  { key: 'top', label: 'Planta', detalle: 'Vista desde arriba' },
  { key: 'side', label: 'Lateral', detalle: 'Vista desde el costado' },
];

/**
 * Vistas en perspectiva extra, definidas solo por la dirección desde la que mira la cámara
 * (en ejes de la escena: X = derecha, Y = arriba, Z = hacia el frente; la cámara se ubica en
 * centro + dirección normalizada × distancia de encuadre). El visor las suma a viewsRef.
 *
 *   iso      (visor)  [ 1, 0.8,  1] → esquina delantera derecha
 *   iso_der  (aquí)   [ 1, 0.8, -1] → esquina posterior derecha: mantiene el lado derecho
 *                                      y muestra el fondo del edificio
 *
 * Para otra esquina basta cambiar el signo: [-1, 0.8, 1] = delantera izquierda,
 * [-1, 0.8, -1] = posterior izquierda.
 */
export const DIRECCIONES_PERSPECTIVA = {
  iso_der: [1, 0.8, -1],
};

const GRADOS = Math.PI / 180;

/**
 * Parámetros de cada proyección oblicua.
 *   dir   → de qué lado mira la cámara (desde dónde se ve el modelo)
 *   up    → hacia dónde apunta "arriba" en la imagen
 *   shear → desplazamiento en pantalla por unidad de profundidad (x' = x + sx·z, y' = y + sy·z,
 *           con z en el espacio de vista: crece hacia el observador)
 */
const OBLICUAS = {
  caballera: {
    dir: () => new THREE.Vector3(0, 0, 1),
    up: () => new THREE.Vector3(0, 1, 0),
    // Lo que está más lejos (z menor) se corre hacia arriba y a la derecha, a 45°, a escala 1.
    shear: { sx: -Math.cos(45 * GRADOS), sy: -Math.sin(45 * GRADOS) },
  },
  militar: {
    dir: () => new THREE.Vector3(0, 1, 0),
    // Planta girada 30°: el eje X de la planta queda a 30° sobre la horizontal.
    up: () => new THREE.Vector3(Math.sin(30 * GRADOS), 0, -Math.cos(30 * GRADOS)),
    // Lo que está más alto (z mayor) se corre hacia arriba en la pantalla, a escala 1.
    shear: { sx: 0, sy: 1 },
  },
};

export const esVistaOblicua = (nombre) => Object.prototype.hasOwnProperty.call(OBLICUAS, nombre);

const esquinas = (box) => {
  const { min, max } = box;
  const pts = [];
  [min.x, max.x].forEach((x) => [min.y, max.y].forEach((y) => [min.z, max.z].forEach((z) => {
    pts.push(new THREE.Vector3(x, y, z));
  })));
  return pts;
};

/**
 * Cámara ortográfica con proyección oblicua que encuadra `box` (THREE.Box3 en
 * coordenadas de mundo) para una imagen de proporción `aspect` (ancho / alto).
 * Devuelve null si el nombre no es una vista oblicua o el volumen está vacío.
 */
export function crearCamaraOblicua(nombre, box, aspect, margen = 0.06) {
  const cfg = OBLICUAS[nombre];
  if (!cfg || !box || box.isEmpty()) return null;

  const center = box.getCenter(new THREE.Vector3());
  const radio = Math.max(box.getSize(new THREE.Vector3()).length() / 2, 1);
  const distancia = radio * 4;

  const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, distancia + radio * 4);
  camera.up.copy(cfg.up());
  camera.position.copy(center).addScaledVector(cfg.dir(), distancia);
  camera.lookAt(center);
  camera.updateMatrixWorld(true);

  const { sx, sy } = cfg.shear;

  // Rectángulo que ocupa el volumen ya proyectado (con el corte aplicado).
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  esquinas(box).forEach((p) => {
    const v = p.applyMatrix4(camera.matrixWorldInverse);
    const x = v.x + sx * v.z;
    const y = v.y + sy * v.z;
    minX = Math.min(minX, x);
    maxX = Math.max(maxX, x);
    minY = Math.min(minY, y);
    maxY = Math.max(maxY, y);
  });

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  let w = Math.max(maxX - minX, 1e-3) * (1 + margen * 2);
  let h = Math.max(maxY - minY, 1e-3) * (1 + margen * 2);
  if (w / h < aspect) w = h * aspect; else h = w / aspect;

  camera.left = cx - w / 2;
  camera.right = cx + w / 2;
  camera.top = cy + h / 2;
  camera.bottom = cy - h / 2;
  camera.updateProjectionMatrix();

  // P · S: primero el corte en el espacio de vista y después la proyección ortográfica.
  const corte = new THREE.Matrix4().set(
    1, 0, sx, 0,
    0, 1, sy, 0,
    0, 0, 1, 0,
    0, 0, 0, 1,
  );
  camera.projectionMatrix.multiply(corte);
  camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
  return camera;
}
