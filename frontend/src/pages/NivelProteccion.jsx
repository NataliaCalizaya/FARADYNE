import React, { useEffect, useState } from 'react';
import { Info, CheckCircle2, MapPin } from 'lucide-react';
import { NivelProteccionForm } from '../components/NivelProteccionForm/NivelProteccionForm';
import { nivelesProteccionApi } from '../api/nivelesProteccion';
import { proyectosApi } from '../api/proyectos';

const FACTORES_POR_DEFECTO = {
  factor_a: '1.0',
  factor_b: '1.0',
  factor_c: '1.0',
  factor_d: '1.0',
  factor_e: '1.0',
};

// Los <select> del form comparan por string con un decimal ("1.0", "0.3"...),
// así que los factores que vienen de la API (numéricos) se normalizan así.
const aFactorString = (n) => Number(n).toFixed(1);

// Encabezado numerado, igual al usado dentro de NivelProteccionForm, para que
// los 7 pasos del cálculo se vean como una única secuencia visual.
const PasoHeader = ({ numero, titulo, colorClass = 'bg-brand-blue' }) => (
  <div className="flex items-center gap-2 mb-3">
    <div className={`w-6 h-6 rounded-full ${colorClass} text-white text-[11px] font-bold flex items-center justify-center shrink-0`}>
      {numero}
    </div>
    <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">{titulo}</h3>
  </div>
);

export const NivelProteccion = ({ idProyecto, onCalculated, onNext }) => {
  const [resultado, setResultado] = useState(null);
  const [nivelSeleccionado, setNivelSeleccionado] = useState(null);
  const [initialFactores, setInitialFactores] = useState(null);
  const [cargandoExistente, setCargandoExistente] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [ubicacionProyecto, setUbicacionProyecto] = useState(null);

  // Al entrar al paso, se intenta recuperar un cálculo ya guardado para el
  // proyecto (factores elegidos + nivel_proteccion_seleccionado). Si no hay
  // nada guardado todavía (404), se arranca con los factores por defecto y
  // el nivel recomendado se toma cuando termine el primer cálculo.
  useEffect(() => {
    let activo = true;

    const cargarExistente = async () => {
      try {
        const existente = await nivelesProteccionApi.obtenerNivelProteccion(idProyecto);
        if (!activo) return;
        setInitialFactores({
          factor_a: aFactorString(existente.factores_riesgo.a),
          factor_b: aFactorString(existente.factores_riesgo.b),
          factor_c: aFactorString(existente.factores_riesgo.c),
          factor_d: aFactorString(existente.factores_riesgo.d),
          factor_e: aFactorString(existente.factores_riesgo.e),
        });
        setNivelSeleccionado(existente.nivel_proteccion_seleccionado);
      } catch (err) {
        if (!activo) return;
        if (err.response?.status !== 404) {
          console.error('Error al obtener el nivel de protección existente:', err);
        }
        setInitialFactores(FACTORES_POR_DEFECTO);
      } finally {
        if (activo) setCargandoExistente(false);
      }
    };

    cargarExistente();
    return () => {
      activo = false;
    };
  }, [idProyecto]);

  // Nombre + ubicación del proyecto, para mostrar junto al Ng adoptado
  // (Paso 1). Si el endpoint falla (proyecto sin ubicación cargada, etc.),
  // simplemente se muestra "No especificada" más abajo.
  useEffect(() => {
    let activo = true;

    const cargarUbicacion = async () => {
      try {
        const proyecto = await proyectosApi.obtenerUbicacionProyecto(idProyecto);
        if (!activo) return;
        setUbicacionProyecto(proyecto.ubicacion || null);
      } catch (err) {
        if (!activo) return;
        console.error('Error al obtener la ubicación del proyecto:', err);
        setUbicacionProyecto(null);
      }
    };

    cargarUbicacion();
    return () => {
      activo = false;
    };
  }, [idProyecto]);

  const handleCalculated = (data) => {
    setResultado(data);
    // Al recalcular (cambio de factores) se preserva la elección manual del
    // usuario (o la ya guardada); solo se inicializa con el recomendado
    // cuando todavía no hay ninguna elección.
    setNivelSeleccionado((prev) => prev || data.nivel_proteccion_recomendado);
  };

  const handleGuardar = async () => {
    if (!resultado) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await nivelesProteccionApi.guardarNivelProteccion({
        id_proyecto: idProyecto,
        factor_a: resultado.factores_riesgo.a,
        factor_b: resultado.factores_riesgo.b,
        factor_c: resultado.factores_riesgo.c,
        factor_d: resultado.factores_riesgo.d,
        factor_e: resultado.factores_riesgo.e,
        nivel_seleccionado: nivelSeleccionado,
      });
      if (onCalculated) onCalculated(saved);
      if (onNext) onNext();
    } catch (err) {
      console.error('Error al guardar nivel de protección:', err);
      setError(err.response?.data?.detail || 'Error al guardar el nivel de protección.');
    } finally {
      setSaving(false);
    }
  };

  const tablaNiveles = resultado?.tabla_niveles || {};

  if (cargandoExistente) {
    return <div className="text-xs text-gray-400">Cargando datos del proyecto...</div>;
  }

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <h1 className="workflow-title text-2xl font-bold font-condensed text-gray-900">
        Nivel de Protección SPDA
      </h1>

      <div className="workflow-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 4 de 7 del workflow</strong> Evaluación de riesgo según Anexo A/B/E/F (IEC 62305 / IRAM 2184 /
          AEA 92305-11) para definir el Nivel de Protección y el radio de esfera rodante.
        </div>
      </div>

      {/* Paso 1: zona/ubicación, Ng adoptado y dimensiones identificadas */}
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
        <PasoHeader numero={1} titulo="Zona y Datos Identificados del Proyecto" />
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-center">
          <div className="p-2 bg-slate-50 border border-slate-200 rounded col-span-2 md:col-span-1 flex flex-col justify-center">
            <div className="text-[10px] text-gray-500 uppercase flex items-center justify-center gap-1">
              <MapPin className="w-3 h-3" /> Ubicación
            </div>
            <div className="text-xs font-bold text-brand-blue leading-tight mt-1">
              {ubicacionProyecto || 'No especificada'}
            </div>
          </div>
          <div className="p-2 bg-slate-50 border border-slate-200 rounded">
            <div className="text-[10px] text-gray-500 uppercase">Longitud (L)</div>
            <div className="text-lg font-bold text-brand-blue">{resultado ? `${resultado.longitud} m` : '—'}</div>
          </div>
          <div className="p-2 bg-slate-50 border border-slate-200 rounded">
            <div className="text-[10px] text-gray-500 uppercase">Anchura (W)</div>
            <div className="text-lg font-bold text-brand-blue">{resultado ? `${resultado.anchura} m` : '—'}</div>
          </div>
          <div className="p-2 bg-slate-50 border border-slate-200 rounded">
            <div className="text-[10px] text-gray-500 uppercase">Altura (H)</div>
            <div className="text-lg font-bold text-brand-blue">{resultado ? `${resultado.altura} m` : '—'}</div>
          </div>
          <div className="p-2 bg-slate-50 border border-slate-200 rounded">
            <div className="text-[10px] text-gray-500 uppercase">Ng adoptado</div>
            <div className="text-lg font-bold text-brand-blue">{resultado ? resultado.densidad_ng : '—'}</div>
          </div>
        </div>
      </div>

      <div className="card-hover bg-white border border-gray-200 rounded-md">
        <div className="p-4">
          <NivelProteccionForm
            idProyecto={idProyecto}
            onCalculated={handleCalculated}
            initialFactores={initialFactores}
          />
        </div>
      </div>

      {resultado && (
        <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-4">
          <PasoHeader numero={7} titulo="Selección Final del Nivel de Protección" colorClass="bg-emerald-600" />

          <div>
            <h3 className="text-xs font-bold text-gray-700 uppercase mb-2">
              Nivel recomendado por el cálculo (Paso 6): <span className="text-emerald-700">{resultado.nivel_proteccion_recomendado}</span>
              {' '}— podés confirmarlo o elegir otro libremente:
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {Object.entries(tablaNiveles).map(([nivel, datos]) => {
                const isSelected = nivelSeleccionado === nivel;
                const isRecomendado = resultado.nivel_proteccion_recomendado === nivel;
                return (
                  <div
                    key={nivel}
                    onClick={() => setNivelSeleccionado(nivel)}
                    className={`p-3 rounded-md border-2 text-center cursor-pointer transition ${
                      isSelected
                        ? 'bg-brand-blue text-white border-brand-blue shadow-md'
                        : 'bg-white text-gray-800 border-gray-200 hover:border-brand-blue'
                    }`}
                  >
                    <div className="text-xs font-bold uppercase tracking-wider">
                      Nivel {nivel} {isRecomendado && <span className="text-[9px]">(recomendado)</span>}
                    </div>
                    <div className="text-xl font-bold font-condensed my-1">R = {datos.radio_esfera_r}m</div>
                    <div className="text-[10px] opacity-80">
                      {datos.corriente_minima_ka} kA · {datos.probabilidad_pct}%
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {nivelSeleccionado && nivelSeleccionado !== resultado.nivel_proteccion_recomendado && (
            <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5 flex items-center gap-2">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              Elegiste un nivel distinto al recomendado por el cálculo. Se guardará tu elección junto con el
              recomendado, para no perder esa trazabilidad.
            </div>
          )}

          {error && <div className="text-xs text-red-600">{error}</div>}

          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={handleGuardar}
              disabled={saving}
              className="px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded text-xs transition"
            >
              {saving ? 'Guardando...' : 'Guardar y Continuar: Posicionar Mástiles →'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default NivelProteccion;