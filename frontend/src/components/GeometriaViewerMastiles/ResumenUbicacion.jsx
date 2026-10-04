import React from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';

const VISTAS = [
  { key: 'split', label: '2D + 3D' },
  { key: '2d', label: 'Solo 2D' },
  { key: '3d', label: 'Solo 3D' },
];

const Metrica = ({ titulo, children }) => (
  <div className="min-w-0">
    <div className="text-gray-500 font-medium text-xs">{titulo}</div>
    {children}
  </div>
);

/**
 * Resumen superior de la página de ubicación de mástiles:
 * métricas (R, mástiles, cobertura), selector de vista, botón de actualizar
 * y advertencias en una franja de ancho completo (no dentro de la grilla de
 * métricas, donde se comprimían en una columna angosta).
 */
export const ResumenUbicacion = ({
  radio = 30,
  totalMastiles = 0,
  porcentajeCobertura = null,
  advertencias = [],
  viewMode = 'split',
  onViewModeChange,
  onRefresh,
  refreshing = false,
}) => {
  const cobertura = porcentajeCobertura != null
    ? `${porcentajeCobertura}%`
    : totalMastiles > 0 ? '—' : '0%';

  return (
    <div className="bg-white border border-gray-200 rounded-md shadow-sm">
      {/* ── Métricas + controles ── */}
      <div className="p-4 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="grid grid-cols-3 gap-6 flex-1 min-w-0">
          <Metrica titulo="Radio Esfera Rodante (R)">
            <div className="text-xl font-bold text-brand-blue font-condensed whitespace-nowrap">
              {radio} m
            </div>
          </Metrica>
          <Metrica titulo="Mástiles Instalados">
            <div className="text-xl font-bold text-gray-800 font-condensed">{totalMastiles}</div>
          </Metrica>
          <Metrica titulo="Cobertura SPDA">
            <div className="text-xl font-bold text-emerald-600 font-condensed">{cobertura}</div>
          </Metrica>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <div className="bg-slate-100 p-1 rounded-md border border-slate-200 flex items-center gap-1">
            {VISTAS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => onViewModeChange?.(key)}
                className={`px-3 py-1 rounded text-xs font-semibold transition ${
                  viewMode === key ? 'bg-brand-blue text-white shadow' : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="px-3 py-1.5 border border-slate-300 hover:bg-slate-100 rounded text-xs font-semibold flex items-center gap-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Actualizar cobertura
          </button>
        </div>
      </div>

      {/* ── Advertencias: ancho completo ── */}
      {advertencias.length > 0 && (
        <div className="border-t border-amber-200 bg-amber-50 px-4 py-3 space-y-1.5 rounded-b-md">
          {advertencias.map((a, i) => (
            <p key={i} className="flex items-start gap-2 text-[11px] leading-snug text-amber-800">
              <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
              <span>{a}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
};

export default ResumenUbicacion;
