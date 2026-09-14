import React, { useState } from 'react';
import { Calculator, ShieldCheck, AlertCircle, CheckCircle2, Zap } from 'lucide-react';
import { nivelesProteccionApi } from '../../api/nivelesProteccion';

const PROTECTIONS = [
  { level: 'Nivel I', radius: 'R = 20m', efficiency: '99%', desc: 'Riesgo Crítico / Explosivos' },
  { level: 'Nivel II', radius: 'R = 30m', efficiency: '95%', desc: 'Comercial / Hospitalario' },
  { level: 'Nivel III', radius: 'R = 45m', efficiency: '90%', desc: 'Residencial / Industrial' },
  { level: 'Nivel IV', radius: 'R = 60m', efficiency: '80%', desc: 'Estructuras Estándar' },
];

export const NivelProteccionForm = ({ idProyecto, onCalculated, onNext }) => {
  const [formData, setFormData] = useState({
    id_proyecto: idProyecto,
    departamento: 'Lima',
    longitud_edificacion: '40',
    anchura_edificacion: '30',
    altura_edificacion: '16',
    factor_ubicacion_cd: '1.0',
    factor_estructura_cb: '1.0',
    factor_contenido_cc: '1.0',
    factor_lineas_ce: '1.0',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [selectedLevel, setSelectedLevel] = useState('Nivel II');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleCalculate = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const data = await nivelesProteccionApi.calculateNivelProteccion({
        ...formData,
        id_proyecto: idProyecto,
      });
      setResult(data);
      if (data.nivel_proteccion_calculado) {
        setSelectedLevel(data.nivel_proteccion_calculado);
      }
      if (onCalculated) {
        onCalculated(data);
      }
    } catch (err) {
      console.error('Risk calculation error:', err);
      setError(err.response?.data?.detail || 'Error al calcular nivel de protección SPDA.');
    } finally {
      setLoading(false);
    }
  };

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

      {/* Form Card */}
      <form onSubmit={handleCalculate} className="bg-white border border-gray-200 rounded-md p-4 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <div className="flex items-center gap-2 text-brand-blue font-bold font-condensed text-base">
            <Zap className="w-5 h-5 text-amber-500 fill-amber-500" />
            <span>Evaluación de Riesgo de Rayos — Norma IEC 62305 / IRAM 2184</span>
          </div>
          <div className="text-xs font-bold text-gray-500">
            Ng (Densidad de descargas) = 2.5 rayos/km²·año
          </div>
        </div>

        {/* Form Inputs Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Ubicación / Región
            </label>
            <select
              name="departamento"
              value={formData.departamento}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            >
              <option value="Lima">Lima (Ng = 2.5)</option>
              <option value="Arequipa">Arequipa (Ng = 3.8)</option>
              <option value="Cusco">Cusco (Ng = 8.2)</option>
              <option value="Puno">Puno (Ng = 12.0)</option>
              <option value="Buenos Aires">Buenos Aires (Ng = 4.5)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Factor Ubicación (Cd)
            </label>
            <select
              name="factor_ubicacion_cd"
              value={formData.factor_ubicacion_cd}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            >
              <option value="0.5">Rodeado de objetos más altos (Cd=0.5)</option>
              <option value="1.0">Rodeado de objetos de igual altura (Cd=1.0)</option>
              <option value="2.0">Estructura aislada en colina/llano (Cd=2.0)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Tipo de Estructura (Cb)
            </label>
            <select
              name="factor_estructura_cb"
              value={formData.factor_estructura_cb}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            >
              <option value="0.5">Hormigón armado / Estructura metálica (Cb=0.5)</option>
              <option value="1.0">Mampostería / Ladrillo tradicional (Cb=1.0)</option>
              <option value="2.0">Estructura inflamable / Madera (Cb=2.0)</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Valor de Contenido (Cc)
            </label>
            <select
              name="factor_contenido_cc"
              value={formData.factor_contenido_cc}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            >
              <option value="0.5">Bajo valor sin equipos sensibles (Cc=0.5)</option>
              <option value="1.0">Estándar residencial / oficinas (Cc=1.0)</option>
              <option value="3.0">Alto valor o sustancias inflamables (Cc=3.0)</option>
            </select>
          </div>
        </div>

        {/* Building Dimensions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1 border-t border-gray-100">
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Longitud Edificación (m)
            </label>
            <input
              type="number"
              name="longitud_edificacion"
              value={formData.longitud_edificacion}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Anchura Edificación (m)
            </label>
            <input
              type="number"
              name="anchura_edificacion"
              value={formData.anchura_edificacion}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Altura Máxima H (m)
            </label>
            <input
              type="number"
              name="altura_edificacion"
              value={formData.altura_edificacion}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs flex items-center gap-1.5 transition"
          >
            <Calculator className="w-4 h-4" />
            {loading ? 'Calculando Riesgo...' : 'Calcular Nivel de Protección'}
          </button>
        </div>
      </form>

      {/* Results Section */}
      {result && (
        <div className="space-y-4 animate-fade-in">
          <div className="bg-white border border-gray-200 rounded-md p-4 shadow-sm">
            <div className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">
              Resultados de la Evaluación de Riesgo (Anexo A)
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-3 bg-slate-50 border border-slate-200 rounded text-center">
                <div className="text-[11px] text-gray-500 font-semibold uppercase">Frecuencia Impactos (Nd)</div>
                <div className="text-2xl font-bold font-condensed text-brand-blue mt-1">
                  {result.frecuencia_impactos_nd || '0.041'}
                </div>
                <div className="text-[10px] text-gray-400 mt-1">impactos directos / año</div>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded text-center">
                <div className="text-[11px] text-gray-500 font-semibold uppercase">Frecuencia Tolerable (Nc)</div>
                <div className="text-2xl font-bold font-condensed text-amber-600 mt-1">
                  {result.frecuencia_tolerable_nc || '1.0×10⁻³'}
                </div>
                <div className="text-[10px] text-gray-400 mt-1">umbral máximo aceptable</div>
              </div>

              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded text-center flex flex-col items-center justify-center">
                <div className="text-[11px] text-emerald-800 font-semibold uppercase">Requisito SPCR</div>
                <div className="text-lg font-bold font-condensed text-emerald-700 mt-1 flex items-center gap-1">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  {result.requiere_spcr ? 'PROTECCIÓN OBLIGATORIA' : 'OPCIONAL'}
                </div>
                <div className="text-[10px] text-emerald-600 font-medium mt-0.5">
                  Eficiencia requerida: {result.eficiencia_proteccion || '≥ 95%'}
                </div>
              </div>
            </div>
          </div>

          {/* Protection Levels Selection Grid */}
          <div>
            <h3 className="text-xs font-bold text-gray-700 uppercase mb-2">
              Seleccionar Nivel de Protección Normalizado
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {PROTECTIONS.map((p) => {
                const isSelected = selectedLevel === p.level || (result.nivel_proteccion_calculado === p.level && !selectedLevel);

                return (
                  <div
                    key={p.level}
                    onClick={() => setSelectedLevel(p.level)}
                    className={`p-3 rounded-md border-2 text-center cursor-pointer transition ${
                      isSelected
                        ? 'bg-brand-blue text-white border-brand-blue shadow-md'
                        : 'bg-white text-gray-800 border-gray-200 hover:border-brand-blue'
                    }`}
                  >
                    <div className="text-xs font-bold uppercase tracking-wider">{p.level}</div>
                    <div className="text-2xl font-bold font-condensed my-1">{p.radius}</div>
                    <div className="text-[10px] opacity-80">{p.desc}</div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Navigation next */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={onNext}
          className="px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-semibold rounded text-xs transition"
        >
          Siguiente: Posicionar Mástiles →
        </button>
      </div>
    </div>
  );
};

export default NivelProteccionForm;
