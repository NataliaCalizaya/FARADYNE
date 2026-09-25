import React, { useState, useEffect } from 'react';
import { Trash2, Ruler, Palette, Pencil, X, Check } from 'lucide-react';
import { ALTURA_STEPS, getMastColor, MAST_COLOR_LEGEND } from '../../api/utilsMastilVisual';
import { SelectField } from '../ui/SelectField';
/**
 * MastilPositioner
 *
 * Panel lateral de control para la ubicación de mástiles captores.
 * Se integra con GeometriaViewerMastiles: este componente NO dibuja la
 * geometría 2D, solo expone controles de altura, la leyenda de colores y
 * la lista de mástiles colocados (con edición de altura, borrado y
 * selección para resaltarlos en los visores).
 *
 * Props:
 *   - masts:            List<MastilResponse>  – mástiles ya persistidos
 *   - mastHeight:       number                – altura para el PRÓXIMO mástil
 *   - onHeightChange:   (height: number) => void
 *   - onDeleteMast:     (id: string) => void
 *   - onSelectMast:     (mast) => void          – clic en una fila de la lista
 *   - selectedMastId:   string|null             – mástil resaltado/en edición
 *   - onUpdateMastHeight: (id, altura) => void  – guardar nueva altura
 *   - onDeselectMast:   () => void
 *   - coverageData:     CoberturaResponse | null
 *   - placing:          boolean               – true mientras se espera un clic en el mapa
 *   - onCancelPlace:    () => void
 */
export const MastilPositioner = ({
  masts = [],
  mastHeight,
  onHeightChange,
  onDeleteMast,
  onSelectMast,
  selectedMastId = null,
  onUpdateMastHeight,
  onDeselectMast,
  coverageData,
  placing = false,
  onCancelPlace,
}) => {
  const handleSlider = (e) => {
    onHeightChange?.(Number(e.target.value));
  };

  // ── Edición de altura del mástil seleccionado ──────────────
  const selectedMast = selectedMastId != null
    ? masts.find((m) => String(m.id) === String(selectedMastId)) || null
    : null;

  const [editHeight, setEditHeight] = useState(mastHeight);

  // Al seleccionar un mástil, arrancar el editor con su altura actual.
  useEffect(() => {
    if (selectedMast) {
      setEditHeight(selectedMast.altura);
    }
  }, [selectedMast?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleEditSlider = (e) => {
    setEditHeight(Number(e.target.value));
  };

  const handleSaveHeight = () => {
    if (selectedMast && onUpdateMastHeight) {
      onUpdateMastHeight(selectedMast.id, editHeight);
    }
  };

  return (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 w-full items-start">
    
    {/* ── COLUMNA 1: Editor y Selector de Altura ── */}
    <div className="flex flex-col gap-4 h-full min-w-0">
      {/* Editor del mástil seleccionado */}
      {selectedMast && (
        <div className="bg-white border-2 border-fuchsia-400 rounded-md p-4 shadow-sm space-y-3 shrink-0">
          <div className="flex items-center justify-between">
            <div className="text-xs font-bold text-fuchsia-700 uppercase flex items-center gap-1.5">
              <Pencil className="w-3.5 h-3.5" />
              Editando Mástil
            </div>
            <button
              type="button"
              onClick={onDeselectMast}
              className="text-gray-400 hover:text-gray-600"
              title="Cerrar"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-center gap-2 text-xs text-gray-600">
            <span
              className="inline-block w-3 h-3 rounded-full border border-white shadow"
              style={{ backgroundColor: getMastColor(selectedMast.altura) }}
            />
            <span>
              Posición: ({Number(selectedMast.posicion_x).toFixed(2)},{' '}
              {Number(selectedMast.posicion_y).toFixed(2)})
            </span>
          </div>
          <p className="text-[11px] text-gray-400 -mt-2">
            Puede arrastrar el mástil en el visor 2D para moverlo; la
            posición se guarda automáticamente al soltarlo.
          </p>

          <div className="space-y-1.5">
            <label className="text-[11px] font-semibold text-gray-600">Nueva altura</label>
            <SelectField
              name="edit-mastil-height"
              value={String(editHeight)}
              onChange={handleEditSlider}
              options={ALTURA_STEPS.map((h) => ({ value: String(h), label: `${h} m` }))}
            />
          </div>

          <div className="flex gap-2 pt-1">
            <button
              type="button"
              onClick={() => onDeleteMast?.(selectedMast.id)}
              className="flex-1 py-1.5 border border-red-400 text-red-600 hover:bg-red-50 rounded text-xs font-semibold flex items-center justify-center gap-1.5"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Eliminar
            </button>
            <button
              type="button"
              onClick={handleSaveHeight}
              disabled={editHeight === selectedMast.altura}
              className="flex-1 py-1.5 bg-fuchsia-600 hover:bg-fuchsia-700 disabled:opacity-40 text-white rounded text-xs font-semibold flex items-center justify-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              Guardar altura
            </button>
          </div>
        </div>
      )}

      {/* Selector de altura para el próximo mástil */}
      <div className="bg-slate-50 border border-gray-200 rounded-md p-4 shadow-sm space-y-4 flex-1">
        <div className="text-xs font-bold text-gray-700 uppercase flex items-center gap-1.5">
          <Ruler className="w-3.5 h-3.5 text-brand-blue" />
          Altura del Próximo Mástil
        </div>

        <div className="space-y-1.5">
          <label htmlFor="mastil-height" className="text-[11px] font-semibold text-gray-600">
            Altura a instalar
          </label>
          <SelectField
            name="mastil-height"
            value={String(mastHeight)}
            onChange={handleSlider}
            options={ALTURA_STEPS.map((h) => ({ value: String(h), label: `${h} m` }))}
          />
        </div>

        <div className="text-center flex items-center justify-center gap-2">
          <span
            className="inline-block w-4 h-4 rounded-full border-2 border-white shadow"
            style={{ backgroundColor: getMastColor(mastHeight) }}
          />
          <span className="text-2xl font-black font-condensed" style={{ color: getMastColor(mastHeight) }}>
            {mastHeight} m
          </span>
          <span className="text-xs text-gray-500">de altura</span>
        </div>
        <div className="border-t border-gray-200 pt-3">
          <div className="text-[11px] font-bold text-gray-600 uppercase mb-2 flex items-center gap-1.5">
            <Palette className="w-3.5 h-3.5 text-brand-blue" />
            Identificación por color
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            {MAST_COLOR_LEGEND.map(({ altura, color }) => (
              <span key={altura} className="flex items-center gap-1.5 text-xs text-gray-600">
                <span className="inline-block w-3 h-3 rounded-full shadow-sm" style={{ backgroundColor: color }} />
                {altura} m
              </span>
            ))}
          </div>
        </div>
        <div className={`rounded border p-3 text-xs font-semibold text-center ${
          placing ? 'bg-amber-50 border-amber-400 text-amber-700' : 'bg-blue-50 border-blue-200 text-brand-blue'
        }`}>
          {placing ? (
            <button type="button" onClick={onCancelPlace} className="w-full underline hover:no-underline">
              Seleccione un punto en el plano 2D · Cancelar
            </button>
          ) : (
            <>Seleccione una altura y use <strong>«Colocar Mástil»</strong> en el visor 2D.</>
          )}
        </div>
      </div>
    </div>

    {/* ── Mástiles y cobertura ── */}
    <div className="flex flex-col gap-4 min-w-0">
    <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col min-h-52 max-h-80 overflow-hidden">
      <div className="text-xs font-bold text-gray-700 uppercase mb-3 shrink-0">
        Mástiles Registrados ({masts.length})
      </div>

      {masts.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-xs text-gray-400 italic text-center px-2">
          No hay mástiles colocados.
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto flex-1 pr-1 custom-scrollbar">
          {masts.map((m, idx) => {
            const isSelected = selectedMastId != null && String(selectedMastId) === String(m.id);
            return (
              <div
                key={m.id || idx}
                onClick={() => onSelectMast?.(m)}
                className={`flex items-center justify-between p-2 border rounded text-xs cursor-pointer transition ${
                  isSelected
                    ? 'bg-fuchsia-50 border-fuchsia-300'
                    : 'bg-slate-50 border-slate-200 hover:bg-slate-100'
                }`}
              >
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: getMastColor(m.altura) }}
                    />
                    <span className="font-bold text-brand-blue">M-{idx + 1}</span>
                    <span className="text-gray-600 font-medium">{m.altura} m</span>
                  </div>
                  <span className="text-[10px] text-gray-400 pl-4">
                    ({Number(m.posicion_x).toFixed(1)}, {Number(m.posicion_y).toFixed(1)})
                  </span>
                </div>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteMast?.(m.id);
                  }}
                  className="text-red-500 hover:text-red-700 p-1 transition"
                  title="Eliminar mástil"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>

    {coverageData && (
      <div className="bg-slate-50 border border-gray-200 rounded-md p-4 shadow-sm grid grid-cols-3 gap-3 text-xs">
        <div className="font-bold text-gray-700 uppercase mb-1">Cobertura SPDA</div>
        <div className="border-l border-gray-200 pl-3">
          <span className="block text-gray-500">Radio esfera rodante</span>
          <span className="font-bold text-brand-blue">
            {coverageData.radio_esfera_rodante_r} m
          </span>
        </div>
        <div className="border-l border-gray-200 pl-3">
          <span className="block text-gray-500">Cobertura total</span>
          <span className="font-black text-emerald-600 text-lg">
            {coverageData.porcentaje_cobertura ?? 0}%
          </span>
        </div>
        <div className="col-span-3 flex justify-between pt-2 border-t border-gray-200">
          <span className="text-gray-500">Puntos desprotegidos</span>
          <span className="font-bold text-amber-600">
            {coverageData.puntos_desprotegidos?.length || 0}
          </span>
        </div>
      </div>
    )}
    </div>
    
  </div>
  );
};

export default MastilPositioner;
