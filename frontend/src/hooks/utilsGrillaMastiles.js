/**
 * Helpers puros de la grilla del visor 2D de mástiles (HU05).
 *
 * Convención del visor (igual que GeometriaViewerMastiles): el punto del plano
 * (x, y) se dibuja en pantalla en (X = y, Y = x). Es decir, el eje x del plano
 * corre en vertical y el eje y corre en horizontal.
 */

/** Pasos de grilla disponibles, en metros (cuadrícula de paso × paso). */
export const GRID_STEPS = [0.5, 1, 2];

/** Índice del paso que se usa por defecto (1 m). */
export const DEFAULT_GRID_INDEX = 1;

/** Separación mínima en pantalla (px) entre líneas dibujadas. */
const MIN_LINE_PX = 6;

/** Cada cuántos metros se resalta una línea de la grilla. */
const MAJOR_EVERY_M = 5;

/**
 * Encuadre del modelo dentro del visor, centrado y con zoom/pan.
 * El ajuste usa la extensión en y para el ancho de pantalla y la extensión en x
 * para el alto, porque el visor intercambia los ejes.
 *
 * @returns {{scale: number, offsetX: number, offsetY: number}}
 */
export function fitTransform(bbox, width, height, zoom = 1, pan = { x: 0, y: 0 }, margin = 30) {
  const cw = width - margin * 2;
  const ch = height - margin * 2;

  if (!bbox || bbox.min_x === undefined) {
    return { scale: zoom, offsetX: margin + pan.x, offsetY: margin + pan.y };
  }

  const extX = Math.max(bbox.max_x - bbox.min_x, 1); // va en vertical
  const extY = Math.max(bbox.max_y - bbox.min_y, 1); // va en horizontal

  const scale = Math.min(cw / extY, ch / extX) * zoom;

  return {
    scale,
    offsetX: margin + (cw - extY * scale) / 2 - bbox.min_y * scale + pan.x,
    offsetY: margin + (ch - extX * scale) / 2 - bbox.min_x * scale + pan.y,
  };
}

/** Lleva un valor al nodo de grilla más cercano (el origen es un nodo). */
export function snapToGrid(value, origin, step) {
  const snapped = origin + Math.round((value - origin) / step) * step;
  return Number(snapped.toFixed(4)); // evita ruido de punto flotante (3.5000000001)
}

/** Nodo de grilla más cercano a un punto del plano. */
export function snapPoint(x, y, origin, step) {
  return [snapToGrid(x, origin.x, step), snapToGrid(y, origin.y, step)];
}

/**
 * Cada cuántos pasos dibujar una línea para que no queden más juntas que
 * MIN_LINE_PX en pantalla. El imán sigue usando el paso real.
 */
export function gridStride(step, scale) {
  return Math.max(1, Math.ceil(MIN_LINE_PX / (step * scale)));
}

/**
 * Valores del plano donde cae una línea de grilla dentro de [min, max].
 *
 * @returns {{value: number, major: boolean}[]}
 */
export function gridLineValues(min, max, origin, step, stride = 1) {
  if (!Number.isFinite(min) || !Number.isFinite(max) || max < min) return [];

  const spacing = step * stride;
  const first = Math.ceil((min - origin) / spacing);
  const last = Math.floor((max - origin) / spacing);

  const out = [];
  for (let k = first; k <= last; k++) {
    const value = origin + k * spacing;
    const resto = Math.abs((k * spacing) % MAJOR_EVERY_M);
    const major = resto < 1e-6 || MAJOR_EVERY_M - resto < 1e-6;
    out.push({ value, major });
  }
  return out;
}


// ============================================================
// SEPARACIÓN MÁXIMA ENTRE MÁSTILES (esfera rodante)
// ============================================================
//
// Una esfera de radio R apoyada en las puntas de una celda (terna/cuaterna)
// cuyo círculo circunscrito tiene radio rho:
//   - toca todas las puntas solo si rho < R
//   - se hunde p = R - sqrt(R² - rho²) por debajo del plano de las puntas
// Para que no llegue al suelo (z = 0) con puntas a altura h hace falta p <= h:
//   rho <= sqrt(h·(2R - h))      (si h >= R, el límite es rho < R)
// Todo lo demás sale de rho:
//   2 mástiles ........ d = 2·rho                (d <= 2R)
//   terna equilátera .. lado = sqrt(3)·rho
//   terna rectángulo .. hipotenusa = 2·rho, catetos = sqrt(2)·rho (isósceles)
//   cuaterna rectángulo a×b .... a² + b² <= (2·rho)²  (p3D = R - sqrt(R² - (a²+b²)/4))
// Se asume que todos los mástiles de la celda tienen la misma altura h.

/** Radio máximo del círculo circunscrito de una celda (m). */
export function radioMaximoCircunscrito(radio, altura) {
  const R = Number(radio);
  const h = Number(altura);
  if (!(R > 0) || !(h > 0)) return 0;
  if (h >= R) return R;
  return Math.sqrt(h * (2 * R - h));
}

/** Penetración de la esfera bajo el plano de las puntas: p = R - sqrt(R² - rho²). */
export function penetracionEsfera(rho, radio) {
  if (rho >= radio) return Infinity;
  return radio - Math.sqrt(radio * radio - rho * rho);
}

/** Altura mínima de las puntas para que una celda de radio circunscrito rho no toque el suelo. */
export function alturaMinimaParaRadio(rho, radio) {
  return penetracionEsfera(rho, radio);
}

/**
 * Distancias máximas recomendadas para R y altura de mástil dados.
 * @returns {{rho:number, par:number, ternaEquilatera:number, ternaCatetos:number,
 *            ternaHipotenusa:number, cuaternaCuadrada:number, cuaternaDiagonal:number}}
 */
export function separacionMaxima(radio, altura) {
  const rho = radioMaximoCircunscrito(radio, altura);
  return {
    rho,
    par: 2 * rho,
    ternaEquilatera: Math.sqrt(3) * rho,
    ternaCatetos: Math.SQRT2 * rho,
    ternaHipotenusa: 2 * rho,
    cuaternaCuadrada: Math.SQRT2 * rho,
    cuaternaDiagonal: 2 * rho,
  };
}

/** Lado b máximo de un rectángulo a × b para una diagonal máxima dada. */
export function ladoMaxRectangulo(a, diagonalMax) {
  const A = Number(a);
  if (!(A >= 0) || A >= diagonalMax) return 0;
  return Math.sqrt(diagonalMax * diagonalMax - A * A);
}

export function formatoMetros(valor) {
  return `${Number(valor).toFixed(2)} m`;
}


// ============================================================
// COTAS TEMPORALES (al colocar o arrastrar un mástil)
// ============================================================

const MIN_TRAMO = 0.005; // m: no se dibujan tramos más cortos

/**
 * Cotas desde un punto del plano hacia los mástiles más cercanos.
 *
 * Para cada mástil M se arma un triángulo rectángulo con el punto P:
 *   P → esquina   tramo horizontal en pantalla (cambia y del plano)
 *   esquina → M   tramo vertical en pantalla   (cambia x del plano)
 *   P → M         diagonal
 *
 * @param {[number, number]} punto  [x, y] del plano
 * @param {Array} masts             mástiles (posicion_x, posicion_y, id)
 * @param {{max?:number, excluirId?:any, dMax?:number|null}} opciones
 *        dMax: distancia diagonal máxima recomendada; si se supera, `excede` = true
 * @returns {Array<{mastId:any, punto:number[], esquina:number[], mastil:number[],
 *                  horizontal:number, vertical:number, diagonal:number,
 *                  excede:boolean}>} ordenado de más cerca a más lejos
 */
export function construirCotas(punto, masts, { max = 3, excluirId = null, dMax = null } = {}) {
  if (!punto || !Array.isArray(masts)) return [];
  const [px, py] = punto;

  return masts
    .filter((m) => excluirId == null || String(m.id) !== String(excluirId))
    .map((m) => {
      const mx = Number(m.posicion_x);
      const my = Number(m.posicion_y);
      const dx = mx - px; // vertical en pantalla
      const dy = my - py; // horizontal en pantalla
      return {
        mastId: m.id,
        punto: [px, py],
        esquina: [px, my],
        mastil: [mx, my],
        horizontal: Math.abs(dy),
        vertical: Math.abs(dx),
        diagonal: Math.hypot(dx, dy),
      };
    })
    .filter((c) => Number.isFinite(c.diagonal) && c.diagonal > MIN_TRAMO)
    .sort((a, b) => a.diagonal - b.diagonal)
    .slice(0, max)
    .map((c) => ({ ...c, excede: dMax != null && c.diagonal > dMax + 1e-9 }));
}

export const MIN_TRAMO_COTA = MIN_TRAMO;

export default {
  GRID_STEPS, DEFAULT_GRID_INDEX, fitTransform, snapToGrid, snapPoint, gridStride, gridLineValues,
  radioMaximoCircunscrito, penetracionEsfera, alturaMinimaParaRadio, separacionMaxima,
  ladoMaxRectangulo, formatoMetros, construirCotas, MIN_TRAMO_COTA,
};