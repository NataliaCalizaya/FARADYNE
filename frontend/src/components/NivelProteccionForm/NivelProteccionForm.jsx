import React, { useState, useCallback } from 'react';
import { Zap, Info, AlertCircle, Calculator, ArrowRight, ShieldCheck, ShieldAlert } from 'lucide-react';
import { nivelesProteccionApi } from '../../api/nivelesProteccion';

// Tabla E.1 - Factor A: Tipo de ocupación
const FACTOR_A_OPTIONS = [
  { value: '0.3', label: 'Casas u otras estructuras de porte equivalente (A=0.3)' },
  { value: '0.7', label: 'Casas con antena exterior (A=0.7)' },
  { value: '1.0', label: 'Fábricas, oficinas y laboratorios (A=1.0)' },
  { value: '1.2', label: 'Oficinas, hoteles, departamentos, residenciales (A=1.2)' },
  { value: '1.3', label: 'Locales de afluencia de público (A=1.3)' },
  { value: '1.7', label: 'Escuelas, hospitales, act. múltiples (A=1.7)' },
];

// Tabla E.2 - Factor B: Tipo de construcción
const FACTOR_B_OPTIONS = [
  { value: '0.2', label: 'Acero recubierto, cubierta no metálica (B=0.2)' },
  { value: '0.4', label: 'Hormigón armado, cubierta no metálica (B=0.4)' },
  { value: '0.8', label: 'Acero/hormigón armado con cubierta metálica (B=0.8)' },
  { value: '1.0', label: 'Mampostería / concreto simple, sin cubierta metálica ni paja (B=1.0)' },
  { value: '1.7', label: 'Madera / mampostería / concreto simple, cubierta metálica (B=1.7)' },
  { value: '2.0', label: 'Cualquier estructura con techo de paja (B=2.0)' },
];

// Tabla E.3 - Factor C: Contenido de la estructura
const FACTOR_C_OPTIONS = [
  { value: '0.3', label: 'Residencias, oficinas, fábricas sin objetos de valor (C=0.3)' },
  { value: '0.8', label: 'Industrial/agrícola con objetos de valor (C=0.8)' },
  { value: '1.0', label: 'Subestaciones, centrales, telefónicas, radio (C=1.0)' },
  { value: '1.3', label: 'Industrias estratégicas, museos, monumentos (C=1.3)' },
  { value: '1.7', label: 'Escuelas, hospitales, guarderías, afluencia pública (C=1.7)' },
];

// Tabla E.4 - Factor D: Localización de la estructura
const FACTOR_D_OPTIONS = [
  { value: '0.4', label: 'Área con estructuras/árboles iguales o más altos (D=0.4)' },
  { value: '1.0', label: 'Área con pocas estructuras de altura similar (D=1.0)' },
  { value: '2.0', label: 'Estructura aislada o mucho más alta que su entorno (D=2.0)' },
];

// Tabla E.5 - Factor E: Topografía
const FACTOR_E_OPTIONS = [
  { value: '0.3', label: 'Planicie (E=0.3)' },
  { value: '1.0', label: 'Elevaciones moderadas, colinas (E=1.0)' },
  { value: '1.3', label: 'Montañas 300–900 m (E=1.3)' },
  { value: '1.7', label: 'Montañas > 900 m (E=1.7)' },
];

const FACTORES_POR_DEFECTO = {
  factor_a: '1.0',
  factor_b: '1.0',
  factor_c: '1.0',
  factor_d: '1.0',
  factor_e: '1.0',
};

// Dibujo simplificado tipo Figura B.1 / B.4 del Anexo B
const FormulaDrawing = ({ length, width, height, marginLateral }) => {
  const marginLabel = marginLateral === 1 ? 'H' : '3H';
  return (
    <svg viewBox="0 0 280 180" className="w-full max-w-xs mx-auto">
      <rect x="20" y="20" width="240" height="140" fill="none" stroke="#94a3b8" strokeDasharray="4 3" rx="18" />
      <rect x="90" y="65" width="100" height="50" fill="#1d4ed8" opacity="0.15" stroke="#1d4ed8" strokeWidth="1.5" />
      <text x="140" y="94" textAnchor="middle" fontSize="10" fill="#1d4ed8" fontWeight="bold">Estructura</text>
      <line x1="20" y1="40" x2="90" y2="40" stroke="#94a3b8" strokeDasharray="2 2" />
      <text x="55" y="35" textAnchor="middle" fontSize="8" fill="#64748b">{marginLabel}</text>
      <text x="140" y="170" textAnchor="middle" fontSize="8" fill="#94a3b8">
        L={length}m · W={width}m · H={height}m
      </text>
    </svg>
  );
};

// Encabezado numerado reutilizado por cada paso del cálculo (Anexo A/B/E/F)
const PasoHeader = ({ numero, titulo, colorClass = 'bg-brand-blue' }) => (
  <div className="flex items-center gap-2 mb-3">
    <div className={`w-6 h-6 rounded-full ${colorClass} text-white text-[11px] font-bold flex items-center justify-center shrink-0`}>
      {numero}
    </div>
    <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">{titulo}</h3>
  </div>
);

// Caja que muestra: fórmula genérica -> fórmula con valores reemplazados -> resultado
const CajaFormula = ({ formulaGenerica, formulaSustituida, resultado, unidad, colorClass = 'text-brand-blue' }) => (
  <div className="bg-slate-50 border border-slate-200 rounded-md p-3 space-y-2 font-mono">
    <div className="text-[10px] text-gray-500 uppercase tracking-wide font-sans font-semibold">Fórmula (Anexo)</div>
    <div className="text-xs text-gray-700">{formulaGenerica}</div>
    <div className="text-[10px] text-gray-500 uppercase tracking-wide font-sans font-semibold pt-1">Reemplazo de valores</div>
    <div className="text-xs text-gray-700 break-words">{formulaSustituida}</div>
    <div className="flex items-baseline gap-2 pt-2 border-t border-slate-200">
      <span className="text-[10px] text-gray-500 uppercase font-sans font-semibold">Resultado</span>
      <span className={`text-lg font-bold font-condensed ${colorClass}`}>
        {resultado} <span className="text-xs font-normal">{unidad}</span>
      </span>
    </div>
  </div>
);

/**
 * `initialFactores`: factores A-E con los que se hace el primer cálculo al
 * montar (formato string, ej. "1.0"). Los manda el padre (NivelProteccion)
 * cuando ya existe un cálculo guardado para el proyecto; si es la primera
 * vez, el padre pasa FACTORES_POR_DEFECTO.
 */
export const NivelProteccionForm = ({ idProyecto, onCalculated, initialFactores }) => {
  const [factores, setFactores] = useState(initialFactores || FACTORES_POR_DEFECTO);
  const [resultado, setResultado] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  // true cuando el usuario tocó un factor después del último cálculo:
  // obliga a apretar "Calcular" de nuevo antes de confiar en los pasos mostrados.
  const [factoresDirty, setFactoresDirty] = useState(false);

  const calcular = useCallback(
    async (valores) => {
      setLoading(true);
      setError(null);
      try {
        const data = await nivelesProteccionApi.calcularNivelProteccion({
          id_proyecto: idProyecto,
          ...valores,
        });
        setResultado(data);
        setFactoresDirty(false);
        if (onCalculated) onCalculated(data);
      } catch (err) {
        console.error('Error al calcular nivel de protección:', err);
        setError(err.response?.data?.detail || 'Error al calcular el nivel de protección SPDA.');
      } finally {
        setLoading(false);
      }
    },
    [idProyecto, onCalculated]
  );

  // Ya NO se calcula automáticamente al montar: los pasos (Ae, Nd, Nc,
  // criterio) solo deben aparecer después de que el usuario apriete el
  // botón "Calcular Frecuencia de Impactos", tanto para un proyecto nuevo
  // como para uno con factores ya guardados.

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFactores((prev) => ({ ...prev, [name]: value }));
    setFactoresDirty(true);
  };

  const handleCalcularClick = () => {
    calcular(factores);
  };

  // --- Construcción de las fórmulas con valores reemplazados (trazabilidad) ---
  let pasoAe = null;
  let pasoNd = null;
  let pasoNc = null;
  let pasoCriterio = null;

  if (resultado) {
    const { longitud: l, anchura: w, altura: h, margen_lateral, area_equivalente_ae, densidad_ng } = resultado;
    const { frecuencia_impactos_nd: nd, frecuencia_tolerable_nc: nc } = resultado;
    const { a, b, c, d, e } = resultado.factores_riesgo || {};

    const esMargenH1 = margen_lateral === 1;
    const formulaAeGenerica = esMargenH1
      ? 'Ae = L·W + 2H·(L+W) + π·H²  [margen lateral H=1, 11m ≤ H ≤ 60m — Fig. B.4]'
      : 'Ae = L·W + 6H·(L+W) + 9·π·H²  [margen lateral H=3, 2m ≤ H ≤ 10m — Fig. B.1]';
    const formulaAeSustituida = esMargenH1
      ? `Ae = ${l}·${w} + 2·${h}·(${l}+${w}) + π·${h}²`
      : `Ae = ${l}·${w} + 6·${h}·(${l}+${w}) + 9·π·${h}²`;

    pasoAe = {
      generica: formulaAeGenerica,
      sustituida: formulaAeSustituida,
      resultado: area_equivalente_ae,
      justificacion: esMargenH1
        ? `Se adoptó margen lateral H=1 porque la altura de la estructura (H=${h} m) está en el rango 11m ≤ H ≤ 60m (Anexo G, AEA 92305-11).`
        : `Se adoptó margen lateral H=3 porque la altura de la estructura (H=${h} m) está en el rango 2m ≤ H ≤ 10m (Anexo G, AEA 92305-11).`,
    };

    pasoNd = {
      generica: 'Nd = Ng · Ae · 10⁻⁶  [descargas directas/año]',
      sustituida: `Nd = ${densidad_ng} · ${area_equivalente_ae} · 10⁻⁶`,
      resultado: nd,
    };

    pasoNc = {
      generica: 'Nc = (A · B · C · D · E) · Nd',
      sustituida: `Nc = (${a} · ${b} · ${c} · ${d} · ${e}) · ${nd}`,
      resultado: nc,
    };

    pasoCriterio = {
      requiereSpcr: resultado.requiere_spcr,
      eficiencia: resultado.eficiencia_proteccion,
      nivel: resultado.nivel_proteccion_recomendado,
      justificacion: resultado.justificacion_nivel,
      nd,
      nc,
    };
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-md flex items-start gap-2 text-xs">
          <AlertCircle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
          <div>
            <strong>Error de Cálculo:</strong> {error}
          </div>
        </div>
      )}

      {/* Paso 2: selección de factores de riesgo */}
      <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-4">
        <PasoHeader numero={2} titulo="Factores de Riesgo — Anexo E (IRAM 2184 / AEA 92305-11)" />

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Factor A · Ocupación</label>
            <select name="factor_a" value={factores.factor_a} onChange={handleChange} className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none">
              {FACTOR_A_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Factor B · Construcción</label>
            <select name="factor_b" value={factores.factor_b} onChange={handleChange} className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none">
              {FACTOR_B_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Factor C · Contenido</label>
            <select name="factor_c" value={factores.factor_c} onChange={handleChange} className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none">
              {FACTOR_C_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Factor D · Localización</label>
            <select name="factor_d" value={factores.factor_d} onChange={handleChange} className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none">
              {FACTOR_D_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">Factor E · Topografía</label>
            <select name="factor_e" value={factores.factor_e} onChange={handleChange} className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none">
              {FACTOR_E_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

        {factoresDirty && !loading && (
          <div className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
            Cambiaste los factores. Apretá "Calcular Frecuencia de Impactos" para actualizar los pasos.
          </div>
        )}

        <div className="flex justify-end pt-1">
          <button
            type="button"
            onClick={handleCalcularClick}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-brand-blue hover:bg-brand-hover disabled:opacity-60 text-white font-semibold rounded text-xs transition"
          >
            <Calculator className="w-4 h-4" />
            {loading ? 'Calculando...' : 'Calcular Frecuencia de Impactos'}
            {!loading && <ArrowRight className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {resultado && (
        <>
          {/* Paso 3: Área colectora equivalente (Ae) */}
          <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
            <PasoHeader numero={3} titulo="Área Colectora Equivalente (Ae) — Anexo B" colorClass="bg-indigo-600" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <CajaFormula
                  formulaGenerica={pasoAe.generica}
                  formulaSustituida={pasoAe.sustituida}
                  resultado={pasoAe.resultado}
                  unidad="m²"
                  colorClass="text-indigo-700"
                />
                <div className="text-[11px] text-gray-500 flex items-start gap-1.5">
                  <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-indigo-500" />
                  <span>{pasoAe.justificacion}</span>
                </div>
              </div>
              <FormulaDrawing
                length={resultado.longitud}
                width={resultado.anchura}
                height={resultado.altura}
                marginLateral={resultado.margen_lateral}
              />
            </div>
          </div>

          {/* Paso 4: Frecuencia esperable de descargas directas (Nd) */}
          <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
            <PasoHeader numero={4} titulo="Frecuencia Esperable de Descargas Directas (Nd) — Anexo D" colorClass="bg-sky-600" />
            <CajaFormula
              formulaGenerica={pasoNd.generica}
              formulaSustituida={pasoNd.sustituida}
              resultado={pasoNd.resultado}
              unidad="descargas directas/año"
              colorClass="text-sky-700"
            />
          </div>

          {/* Paso 5: Frecuencia aceptable corregida (Nc) */}
          <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
            <PasoHeader numero={5} titulo="Frecuencia Aceptable Corregida (Nc) — Anexo E" colorClass="bg-amber-600" />
            <CajaFormula
              formulaGenerica={pasoNc.generica}
              formulaSustituida={pasoNc.sustituida}
              resultado={pasoNc.resultado}
              unidad=""
              colorClass="text-amber-700"
            />
          </div>

          {/* Paso 6: Criterio F.1 - necesidad de SPCR y nivel recomendado */}
          <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
            <PasoHeader numero={6} titulo="Criterio F.1 — Nivel de Protección Recomendado" colorClass="bg-emerald-600" />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
              <div className="p-2 bg-slate-50 border border-slate-200 rounded text-center">
                <div className="text-[10px] text-gray-500 uppercase">Nd (impactos directos)</div>
                <div className="text-sm font-bold text-gray-800">{pasoCriterio.nd}</div>
              </div>
              <div className="p-2 bg-slate-50 border border-slate-200 rounded text-center">
                <div className="text-[10px] text-gray-500 uppercase">Nc (frec. aceptable)</div>
                <div className="text-sm font-bold text-gray-800">{pasoCriterio.nc}</div>
              </div>
            </div>

            <div
              className={`p-3 rounded-md border flex items-start gap-2 ${
                pasoCriterio.requiereSpcr
                  ? 'bg-amber-50 border-amber-200 text-amber-800'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-800'
              }`}
            >
              {pasoCriterio.requiereSpcr ? (
                <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
              ) : (
                <ShieldCheck className="w-5 h-5 shrink-0 mt-0.5" />
              )}
              <div>
                <div className="text-xs font-bold uppercase">
                  {pasoCriterio.requiereSpcr ? 'Se requiere SPCR (Nd > Nc)' : 'No se requiere SPCR obligatorio (Nd ≤ Nc)'}
                </div>
                {pasoCriterio.requiereSpcr && pasoCriterio.eficiencia !== null && pasoCriterio.eficiencia !== undefined && (
                  <div className="text-[11px] mt-1">
                    Eficiencia requerida: <strong>E = 1 − (Nc/Nd) = {pasoCriterio.eficiencia}</strong> → Tabla F.1
                  </div>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-[10px] uppercase font-semibold">Nivel recomendado</span>
                  <span className="text-lg font-bold font-condensed">{pasoCriterio.nivel}</span>
                </div>
                <div className="text-[11px] mt-1 opacity-90">{pasoCriterio.justificacion}</div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default NivelProteccionForm;