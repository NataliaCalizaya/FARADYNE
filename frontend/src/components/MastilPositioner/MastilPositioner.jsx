import React, { useState, useEffect } from 'react';
import { Trash2, MapPin, Ruler, Palette, Pencil, X, Check } from 'lucide-react';
import { ALTURA_STEPS, getMastColor, MAST_COLOR_LEGEND } from '../../api/utilsMastilVisual';

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
  const sliderIndex = ALTURA_STEPS.indexOf(mastHeight);

  const handleSlider = (e) => {
    const idx = parseInt(e.target.value, 10);
    onHeightChange?.(ALTURA_STEPS[idx]);
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

  const editIndex = ALTURA_STEPS.indexOf(editHeight);

  const handleEditSlider = (e) => {
    const idx = parseInt(e.target.value, 10);
    setEditHeight(ALTURA_STEPS[idx]);
  };

  const handleSaveHeight = () => {
    if (selectedMast && onUpdateMastHeight) {
      onUpdateMastHeight(selectedMast.id, editHeight);
    }
  };

  return (
  <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 w-full items-stretch">
    
    {/* ── COLUMNA 1: Editor y Selector de Altura ── */}
    <div className="flex flex-col gap-4 h-full">
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

          <div className="space-y-2">
            <input
              type="range"
              min={0}
              max={ALTURA_STEPS.length - 1}
              step={1}
              value={editIndex >= 0 ? editIndex : 0}
              onChange={handleEditSlider}
              className="w-full accent-fuchsia-600"
            />
            <div className="flex justify-between text-[10px] font-medium select-none">
              {ALTURA_STEPS.map((h) => (
                <span
                  key={h}
                  style={{ color: getMastColor(h) }}
                  className={h === editHeight ? 'font-bold' : 'opacity-50'}
                >
                  {h} m
                </span>
              ))}
            </div>
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
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-3 flex-1">
        <div className="text-xs font-bold text-gray-700 uppercase flex items-center gap-1.5">
          <Ruler className="w-3.5 h-3.5 text-brand-blue" />
          Altura del Próximo Mástil
        </div>

        <div className="space-y-2">
          <input
            id="mastil-height-slider"
            type="range"
            min={0}
            max={ALTURA_STEPS.length - 1}
            step={1}
            value={sliderIndex >= 0 ? sliderIndex : 1}
            onChange={handleSlider}
            className="w-full accent-brand-blue"
          />
          <div className="flex justify-between text-[10px] font-medium select-none">
            {ALTURA_STEPS.map((h) => (
              <span
                key={h}
                style={{ color: getMastColor(h) }}
                className={h === mastHeight ? 'font-bold' : 'opacity-50'}
              >
                {h} m
              </span>
            ))}
          </div>
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
      </div>
    </div>

    {/* ── COLUMNA 2: Leyenda de colores ── */}
    <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm h-full">
      <div className="text-[11px] font-bold text-gray-600 uppercase mb-3 flex items-center gap-1.5">
        <Palette className="w-3.5 h-3.5 text-brand-blue" />
        Identificación por color
      </div>
      <div className="flex flex-col gap-2">
        {MAST_COLOR_LEGEND.map(({ altura, color }) => (
          <span key={altura} className="flex items-center gap-2 text-xs text-gray-600">
            <span
              className="inline-block w-3 h-3 rounded-full shadow-sm"
              style={{ backgroundColor: color }}
            />
            {altura} m
          </span>
        ))}
      </div>
    </div>

    {/* ── COLUMNA 3: Instrucción de colocación ── */}
    <div
      className={`rounded-md border p-4 text-xs font-semibold flex flex-col justify-center gap-3 transition-all h-full text-center ${
        placing
          ? 'bg-amber-50 border-amber-400 text-amber-700 animate-pulse'
          : 'bg-blue-50 border-blue-200 text-brand-blue'
      }`}
    >
      <MapPin className="w-6 h-6 mx-auto mb-1" />
      {placing ? (
        <>
          <span>Haga clic sobre la geometría 2D para colocar el mástil...</span>
          {onCancelPlace && (
            <button
              type="button"
              onClick={onCancelPlace}
              className="text-amber-700 underline hover:no-underline mt-2 inline-block"
            >
              Cancelar
            </button>
          )}
        </>
      ) : (
        <span>
          Seleccione la altura y haga clic en el botón{' '}
          <strong>«Colocar Mástil»</strong> debajo del visor 2D.
        </span>
      )}
    </div>

    {/* ── COLUMNA 4: Lista de mástiles colocados ── */}
    <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col h-full overflow-hidden max-h-64 lg:max-h-none">
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

    {/* ── COLUMNA 5: Estadísticas de cobertura ── */}
    {coverageData ? (
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col justify-center space-y-3 text-xs h-full">
        <div className="font-bold text-gray-700 uppercase mb-1">Cobertura SPDA</div>
        <div className="flex justify-between py-1 border-b border-gray-100">
          <span className="text-gray-500">Radio esfera rodante:</span>
          <span className="font-bold text-brand-blue">
            {coverageData.radio_esfera_rodante_r} m
          </span>
        </div>
        <div className="flex justify-between py-1 border-b border-gray-100">
          <span className="text-gray-500">Puntos desprotegidos:</span>
          <span className="font-bold text-amber-600">
            {coverageData.puntos_desprotegidos?.length || 0}
          </span>
        </div>
        <div className="flex justify-between py-1 items-center mt-2">
          <span className="text-gray-500">Cobertura total:</span>
          <span className="font-black text-emerald-600 text-lg">
            {coverageData.porcentaje_cobertura ?? 0}%
          </span>
        </div>
      </div>
    ) : (
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm flex items-center justify-center text-xs text-gray-400 italic text-center h-full">
        Sin datos de cobertura.
      </div>
    )}
    
  </div>
  );
};

export default MastilPositioner;