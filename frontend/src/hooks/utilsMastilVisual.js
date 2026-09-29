/**
 * Config visual compartida para mástiles captores (HU05).
 *
 * Un mismo criterio de color por altura en el visor 2D
 * (GeometriaViewerMastiles), el panel lateral (MastilPositioner) y el
 * visor 3D (Modelo3DViewer), para poder identificar el tipo de mástil de
 * un vistazo en cualquiera de las tres vistas.
 */

export const ALTURA_STEPS = [0.5, 1, 1.5, 2, 2.5];

const COLOR_POR_ALTURA = {
  0.5: '#2563eb', // azul
  1: '#16a34a',   // verde
  1.5: '#eab308', // amarillo
  2: '#ea580c',   // naranja
  2.5: '#dc2626', // rojo
};

const COLOR_DEFECTO = '#e07a10';

/**
 * Color hexadecimal asociado a una altura de mástil.
 * Si la altura no coincide exactamente con un paso de ALTURA_STEPS
 * (ej. un valor cargado manualmente), usa el color del paso más cercano.
 */
export function getMastColor(altura) {
  const valor = Number(altura);

  if (!Number.isFinite(valor)) {
    return COLOR_DEFECTO;
  }

  let masCercana = ALTURA_STEPS[0];
  let mejorDistancia = Math.abs(valor - masCercana);

  for (const paso of ALTURA_STEPS) {
    const distancia = Math.abs(valor - paso);

    if (distancia < mejorDistancia) {
      mejorDistancia = distancia;
      masCercana = paso;
    }
  }

  return COLOR_POR_ALTURA[masCercana] || COLOR_DEFECTO;
}

/** Para pintar una leyenda "altura -> color" en cualquier panel. */
export const MAST_COLOR_LEGEND = ALTURA_STEPS.map((altura) => ({
  altura,
  color: COLOR_POR_ALTURA[altura],
}));

export default { ALTURA_STEPS, getMastColor, MAST_COLOR_LEGEND };
