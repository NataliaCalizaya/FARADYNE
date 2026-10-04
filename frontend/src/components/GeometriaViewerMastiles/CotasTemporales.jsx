import React from 'react';
import { Group, Line, Rect, Text } from 'react-konva';

import { formatoMetros, MIN_TRAMO_COTA } from '../../hooks/utilsGrillaMastiles';

const COLORS = {
  tramo: '#64748b',     // catetos (horizontal / vertical)
  diagonal: '#059669',  // diagonal dentro del límite recomendado
  excede: '#dc2626',    // diagonal que supera el máximo recomendado
};

/** Etiqueta con fondo blanco centrada en (x, y) de pantalla. */
const Etiqueta = ({ x, y, text, color }) => {
  const w = text.length * 5.4 + 8;
  const h = 14;
  return (
    <Group x={x} y={y} listening={false}>
      <Rect x={-w / 2} y={-h / 2} width={w} height={h} fill="#fff" stroke={color}
            strokeWidth={1} cornerRadius={3} opacity={0.95} />
      <Text text={text} x={-w / 2} y={-h / 2} width={w} height={h}
            align="center" verticalAlign="middle" fontSize={9} fontStyle="bold" fill={color} />
    </Group>
  );
};

/**
 * Cotas temporales (triángulo rectángulo punto → mástil) mientras se coloca o
 * se arrastra un mástil. Va dentro de una <Layer listening={false}>.
 *
 * Props:
 *  - cotas: salida de construirCotas()
 *  - transformPoint: (x, y) del plano -> [pantallaX, pantallaY]
 */
export const CotasTemporales = ({ cotas = [], transformPoint }) => (
  <>
    {cotas.map((c) => {
      const [pX, pY] = transformPoint(c.punto[0], c.punto[1]);
      const [cX, cY] = transformPoint(c.esquina[0], c.esquina[1]);
      const [mX, mY] = transformPoint(c.mastil[0], c.mastil[1]);
      const colorDiag = c.excede ? COLORS.excede : COLORS.diagonal;

      return (
        <Group key={`cota-${c.mastId}`} listening={false}>
          {/* Catetos (se omiten si el mástil está alineado) */}
          {c.horizontal > MIN_TRAMO_COTA && c.vertical > MIN_TRAMO_COTA && (
            <Line points={[pX, pY, cX, cY, mX, mY]} stroke={COLORS.tramo}
                  strokeWidth={1} dash={[4, 3]} />
          )}
          {/* Diagonal */}
          <Line points={[pX, pY, mX, mY]} stroke={colorDiag} strokeWidth={1.8}
                dash={c.excede ? [6, 3] : undefined} />

          {c.horizontal > MIN_TRAMO_COTA && c.vertical > MIN_TRAMO_COTA && (
            <>
              <Etiqueta
                x={(pX + cX) / 2}
                y={(pY + cY) / 2 + (mY > pY ? -11 : 11)}
                text={formatoMetros(c.horizontal)}
                color={COLORS.tramo}
              />
              <Etiqueta
                x={(cX + mX) / 2 + (pX < mX ? 22 : -22)}
                y={(cY + mY) / 2}
                text={formatoMetros(c.vertical)}
                color={COLORS.tramo}
              />
            </>
          )}
          <Etiqueta
            x={(pX + mX) / 2}
            y={(pY + mY) / 2}
            text={`${formatoMetros(c.diagonal)}${c.excede ? ' ⚠' : ''}`}
            color={colorDiag}
          />
        </Group>
      );
    })}
  </>
);

export default CotasTemporales;
