import React, { useMemo, useState } from 'react';
import { Lightbulb, AlertTriangle } from 'lucide-react';

import {
  separacionMaxima, ladoMaxRectangulo, alturaMinimaParaRadio, formatoMetros,
} from '../../hooks/utilsGrillaMastiles';

const SEPARACIONES_EJEMPLO = [5, 10, 15, 20];

/**
 * Recomendaciones de separación máxima entre mástiles según el radio de la
 * esfera rodante y la altura del mástil que se va a crear (HU05).
 *
 * Props:
 *  - radio:        R de la esfera rodante (m)
 *  - altura:       altura del próximo mástil (m, sobre z = 0)
 *  - cotaCubierta: opcional, cota de la cubierta más alta (m). La esfera no
 *                  debe tocarla, así que se descuenta de la altura útil.
 */
export const RecomendacionesMastiles = ({
  radio = 30, altura = 1, cotaCubierta = 0, className = '',
}) => {
  const hUtil = Math.max(0, Number(altura) - Number(cotaCubierta || 0));
  const sep = useMemo(() => separacionMaxima(radio, hUtil), [radio, hUtil]);
  const [ladoA, setLadoA] = useState('');

  const a = ladoA === '' ? null : Number(ladoA);
  const bMax = a != null ? ladoMaxRectangulo(a, sep.cuaternaDiagonal) : null;

  const filas = [
    ['2 mástiles (distancia)', sep.par, 'd ≤ 2·ρ'],
    ['Terna equilátera (lado)', sep.ternaEquilatera, 'lado ≤ √3·ρ'],
    ['Terna rectángula isósceles (catetos)', sep.ternaCatetos, `hipotenusa ≤ ${formatoMetros(sep.ternaHipotenusa)}`],
    ['Cuaterna cuadrada (lado)', sep.cuaternaCuadrada, `diagonal ≤ ${formatoMetros(sep.cuaternaDiagonal)}`],
  ];

  return (
    <div className={`bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-3 ${className}`}>
      <div className="flex items-center gap-2 text-xs font-bold text-gray-600 uppercase">
        <Lightbulb className="w-4 h-4 text-amber-500" />
        Separación máxima recomendada · R = {radio} m · mástil de {Number(altura).toFixed(1)} m
      </div>

      {hUtil <= 0 ? (
        <div className="flex items-center gap-2 text-[11px] text-red-700">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          La altura del mástil no supera la cota de la cubierta: la esfera tocaría la cubierta.
        </div>
      ) : (
        <>
          <p className="text-[11px] text-gray-500 leading-snug">
            Para que la esfera se apoye en las puntas sin llegar al suelo, el círculo que pasa por
            ellas debe tener radio ρ ≤ √(h·(2R − h)) = <strong>{formatoMetros(sep.rho)}</strong>.
            Se asume que todos los mástiles de la terna/cuaterna tienen esta altura.
          </p>

          <table className="w-full text-xs">
            <tbody>
              {filas.map(([nombre, valor, nota]) => (
                <tr key={nombre} className="border-t border-gray-100">
                  <td className="py-1 text-gray-600">{nombre}</td>
                  <td className="py-1 font-bold text-emerald-700 tabular-nums text-right">≤ {formatoMetros(valor)}</td>
                  <td className="py-1 pl-3 text-[10px] text-gray-400">{nota}</td>
                </tr>
              ))}
              <tr className="border-t border-gray-100">
                <td className="py-1 text-gray-600">
                  Cuaterna rectangular: lado a =
                  <input
                    type="number" min="0" step="0.5" value={ladoA}
                    onChange={(e) => setLadoA(e.target.value)}
                    className="mx-1 w-16 border border-gray-300 rounded px-1 py-0.5 text-xs"
                    placeholder="m"
                  />
                  → lado b
                </td>
                <td className="py-1 font-bold text-emerald-700 tabular-nums text-right">
                  {bMax != null ? `≤ ${formatoMetros(bMax)}` : '—'}
                </td>
                <td className="py-1 pl-3 text-[10px] text-gray-400">a² + b² ≤ (2·ρ)²</td>
              </tr>
            </tbody>
          </table>

          {sep.rho < 4 && (
            <div className="flex items-start gap-2 text-[11px] text-amber-700">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              Con esta altura la separación admisible es muy corta. Un mástil más alto permite separarlos más.
            </div>
          )}

          <div className="text-[11px] text-gray-500">
            <div className="font-semibold mb-1">Altura mínima para no tocar el suelo (terna equilátera):</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {SEPARACIONES_EJEMPLO.map((s) => {
                const hMin = alturaMinimaParaRadio(s / Math.sqrt(3), radio) + Number(cotaCubierta || 0);
                const ok = Number(altura) >= hMin;
                return (
                  <span key={s} className={ok ? 'text-emerald-700' : 'text-red-600'}>
                    lado {s} m → h ≥ {Number.isFinite(hMin) ? hMin.toFixed(2) : '∞'} m
                  </span>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default RecomendacionesMastiles;
