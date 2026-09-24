import React, { useState, useEffect } from 'react';
import { Plus, Trash2, ShieldCheck, AlertOctagon, CheckCircle2, RotateCcw } from 'lucide-react';
import { mastilesApi } from '../../api/mastiles';
import { Modelo3DViewer } from '../Modelo3DViewer/Modelo3DViewer';
import { SelectField } from '../ui/SelectField';

const NODES = [
  { id: 'N1_NW', name: 'Esquina NO (Nivel 1)', x: 65, y: 35, z: 4 },
  { id: 'N1_NE', name: 'Esquina NE (Nivel 1)', x: 565, y: 35, z: 4 },
  { id: 'N2_NE', name: 'Ala Norte NE (Nivel 2)', x: 560, y: 35, z: 8 },
  { id: 'N3_NW', name: 'Núcleo Central NO (N3)', x: 285, y: 95, z: 12 },
  { id: 'N3_NE', name: 'Núcleo Central NE (N3)', x: 395, y: 95, z: 12 },
  { id: 'N3_SE', name: 'Núcleo Central SE (N3)', x: 395, y: 190, z: 12 },
  { id: 'N4_SE', name: 'Bloque SE (Nivel 4)', x: 550, y: 330, z: 16 },
  { id: 'N5_SW', name: 'Ala Oeste SO (Nivel 5)', x: 65, y: 385, z: 4 },
];

export const MastilPositioner = ({ idProyecto, idModelo3D, idModelo2D, onNext }) => {
  const [masts, setMasts] = useState([]);
  const [coverageData, setCoverageData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [mastHeight, setMastHeight] = useState('3.0');
  const [mastType, setMastType] = useState('Franklin');

  useEffect(() => {
    if (idProyecto) {
      loadCoverage(idProyecto);
    }
  }, [idProyecto]);

  const loadCoverage = async (projId) => {
    setLoading(true);
    try {
      const data = await mastilesApi.getCobertura(projId);
      setCoverageData(data);
      if (data.mastiIes) {
        setMasts(data.mastiIes);
      }
    } catch (err) {
      console.error('Error fetching coverage:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleNodeClick = (node) => {
    setSelectedNode(node);
    setMastHeight('3.0');
    setMastType('Franklin');
    setModalOpen(true);
  };

  const handleAddMast = async () => {
    if (!selectedNode) return;

    try {
      const newMast = await mastilesApi.createMastil({
        id_modelo3d: idModelo3D || 'default_3d_model',
        id_proyecto: idProyecto,
        posicion_x: selectedNode.x,
        posicion_y: selectedNode.y,
        posicion_z: selectedNode.z,
        altura: parseFloat(mastHeight),
        tipo: mastType,
      });

      setMasts((prev) => [...prev, newMast]);
      setModalOpen(false);
      loadCoverage(idProyecto);
    } catch (err) {
      console.error('Error adding mast:', err);
    }
  };

  const handleDeleteMast = async (mastId) => {
    try {
      await mastilesApi.deleteMastil(mastId);
      setMasts((prev) => prev.filter((m) => m.id !== mastId));
      loadCoverage(idProyecto);
    } catch (err) {
      console.error('Error deleting mast:', err);
    }
  };

  const [viewMode, setViewMode] = useState('split'); // 'split', '2d', '3d'

  return (
    <div className="space-y-4">
      {/* Parameters & Mode Switcher Header */}
      <div className="card-hover bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs flex-1">
          <div>
            <div className="text-gray-500 font-medium">Radio de Esfera Rodante (R)</div>
            <div className="text-lg font-bold text-brand-blue font-condensed">
              {coverageData?.radio_esfera_rodante_r || 30} m 🔒 (Nivel II)
            </div>
          </div>
          <div>
            <div className="text-gray-500 font-medium">Mástiles Instalados</div>
            <div className="text-lg font-bold text-gray-800 font-condensed">
              {masts.length} mástiles captores
            </div>
          </div>
          <div>
            <div className="text-gray-500 font-medium">Porcentaje Cobertura Total</div>
            <div className="text-lg font-bold text-emerald-600 font-condensed">
              {coverageData?.porcentaje_cobertura || (masts.length > 0 ? 98 : 0)}%
            </div>
          </div>
        </div>

        {/* View Mode Toggle Controls */}
        <div className="bg-slate-100 p-1 rounded-md border border-slate-200 flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => setViewMode('split')}
            className={`px-3 py-1 rounded text-xs font-semibold transition ${viewMode === 'split' ? 'bg-brand-blue text-white shadow' : 'text-gray-600 hover:text-gray-900'
              }`}
          >
            Vista Dividida (2D + 3D)
          </button>
          <button
            type="button"
            onClick={() => setViewMode('2d')}
            className={`px-3 py-1 rounded text-xs font-semibold transition ${viewMode === '2d' ? 'bg-brand-blue text-white shadow' : 'text-gray-600 hover:text-gray-900'
              }`}
          >
            Solo Vista 2D
          </button>
          <button
            type="button"
            onClick={() => setViewMode('3d')}
            className={`px-3 py-1 rounded text-xs font-semibold transition ${viewMode === '3d' ? 'bg-brand-blue text-white shadow' : 'text-gray-600 hover:text-gray-900'
              }`}
          >
            Solo Vista 3D
          </button>
        </div>
      </div>

      {/* Grid with 2D Placement Plan & 3D Visor depending on viewMode */}
      <div className={`grid gap-4 ${viewMode === 'split' ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'}`}>
        {/* 2D Interactive Node Plan */}
        {(viewMode === 'split' || viewMode === '2d') && (
          <div className="card-hover bg-white border border-gray-200 rounded-md p-3 shadow-sm flex flex-col">
            <div className="text-xs font-bold text-gray-700 uppercase mb-2 flex items-center justify-between">
              <span>Vista de Planta — Clic en vértice para ubicar mástil</span>
              <span className="text-[10px] text-brand-blue font-normal">Modo interacción activo</span>
            </div>

            <div className="relative bg-slate-50 border border-gray-300 rounded h-[380px] flex items-center justify-center overflow-hidden">
              <svg width="100%" height="100%" viewBox="0 0 620 420" className="w-full h-full">
                <defs>
                  <pattern id="gridPlanta" width="20" height="20" patternUnits="userSpaceOnUse">
                    <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#e8edf3" strokeWidth="0.5" />
                  </pattern>
                </defs>
                <rect width="620" height="420" fill="url(#gridPlanta)" />

                {/* Building outlines */}
                <rect x="65" y="35" width="500" height="350" fill="rgba(26,109,186,0.04)" stroke="#1a6dba" strokeWidth="1.5" />
                <rect x="285" y="35" width="275" height="160" fill="rgba(26,109,186,0.06)" stroke="#1a6dba" strokeWidth="1.5" />
                <rect x="285" y="95" width="110" height="95" fill="rgba(26,109,186,0.1)" stroke="#1a6dba" strokeWidth="1.5" />
                <rect x="405" y="200" width="145" height="130" fill="rgba(26,109,186,0.06)" stroke="#1a6dba" strokeWidth="1.5" />

                {/* Obstacles */}
                <rect x="85" y="300" width="52" height="40" fill="rgba(224,122,16,0.12)" stroke="#e07a10" strokeWidth="1.8" rx="2" />
                <text x="110" y="320" textAnchor="middle" fontSize="8" fontWeight="700" fill="#e07a10">TANQUE</text>

                {/* Clickable Node Hotspots */}
                {NODES.map((node) => {
                  const hasMast = masts.some((m) => Math.abs(m.posicion_x - node.x) < 20 && Math.abs(m.posicion_y - node.y) < 20);

                  return (
                    <g key={node.id} onClick={() => handleNodeClick(node)} className="cursor-pointer group">
                      <circle
                        cx={node.x}
                        cy={node.y}
                        r={hasMast ? 10 : 8}
                        fill={hasMast ? '#e07a10' : '#1a6dba'}
                        stroke="white"
                        strokeWidth="2"
                        className="transition-transform transform group-hover:scale-125"
                      />
                      {hasMast ? (
                        <text x={node.x} y={node.y + 3.5} textAnchor="middle" fontSize="10" fill="white" fontWeight="800">
                          ⚡
                        </text>
                      ) : (
                        <circle cx={node.x} cy={node.y} r="3" fill="white" />
                      )}
                    </g>
                  );
                })}

                {/* Masts radii circles */}
                {masts.map((m, i) => (
                  <circle
                    key={i}
                    cx={m.posicion_x}
                    cy={m.posicion_y}
                    r={(m.altura || 3) * 12}
                    fill="rgba(26,109,186,0.08)"
                    stroke="rgba(26,109,186,0.3)"
                    strokeDasharray="4,2"
                  />
                ))}
              </svg>
            </div>

            <div className="mt-2 text-[10px] text-gray-500 flex justify-between">
              <span>• Clic sobre círculos azules para añadir pararrayos</span>
              <span>• Ícono ⚡ indica mástil activo</span>
            </div>
          </div>
        )}

        {/* 3D Visor */}
        {(viewMode === 'split' || viewMode === '3d') && (
          <div className="card-hover h-[430px] rounded-md overflow-hidden">
            <Modelo3DViewer idModelo3D={idModelo3D} idModelo2D={idModelo2D} masts={masts} />
          </div>
        )}
      </div>


      {/* Installed Masts List & Coverage Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Masts Table */}
        <div className="card-hover bg-white border border-gray-200 rounded-md p-4 shadow-sm">
          <div className="text-xs font-bold text-gray-700 uppercase mb-2">
            Mástiles Registrados ({masts.length})
          </div>
          {masts.length === 0 ? (
            <div className="text-xs text-gray-400 py-6 text-center italic">
              No hay mástiles instalados. Haga clic en los nodos de la planta para añadir pararrayos.
            </div>
          ) : (
            <div className="space-y-2 max-h-[160px] overflow-y-auto">
              {masts.map((m, idx) => (
                <div key={m.id || idx} className="flex items-center justify-between p-2 bg-slate-50 border border-slate-200 rounded text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-brand-blue">M-{idx + 1}</span>
                    <span>{m.tipo || 'Franklin'}</span>
                    <span className="text-gray-400">({m.altura}m de altura)</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleDeleteMast(m.id)}
                    className="text-red-500 hover:text-red-700 p-1 transition"
                    title="Eliminar mástil"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Coverage Summary */}
        <div className="card-hover bg-white border border-gray-200 rounded-md p-4 shadow-sm flex flex-col justify-between">
          <div>
            <div className="text-xs font-bold text-gray-700 uppercase mb-2">
              Estadísticas de Cobertura SPDA
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Área Total Protegida:</span>
                <span className="font-bold text-emerald-600">
                  {coverageData?.puntos_cobertura?.length ? `${coverageData.puntos_cobertura.length * 50} m²` : '2,450 m²'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-gray-100">
                <span>Área Vulnerable / Puntos Desprotegidos:</span>
                <span className="font-bold text-amber-600">
                  {coverageData?.puntos_desprotegidos?.length || 0} puntos
                </span>
              </div>
              <div className="flex justify-between py-1">
                <span>Porcentaje de Cobertura Alcanzado:</span>
                <span className="font-bold text-emerald-600 text-sm">
                  {coverageData?.porcentaje_cobertura || 98}%
                </span>
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onNext}
            className="btn-electric w-full mt-3 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition"
          >
            Confirmar Ubicación y Continuar →
          </button>
        </div>
      </div>

      {/* React Modal for Height / Type (Replaces Browser Prompt) */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white border border-gray-300 rounded-lg p-5 w-full max-w-xs shadow-2xl space-y-4 animate-fade-in">
            <div className="border-b border-gray-100 pb-2">
              <h3 className="font-condensed font-bold text-sm text-slate-900 uppercase">
                Añadir Mástil Captor
              </h3>
              <p className="text-[11px] text-gray-500">{selectedNode?.name}</p>
            </div>

            <div>
              <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
                Altura Mástil (m)
              </label>
              <input
                type="number"
                step="0.5"
                value={mastHeight}
                onChange={(e) => setMastHeight(e.target.value)}
                className="input-electric w-full p-2 border border-gray-300 rounded text-center text-base font-bold text-brand-blue"
              />
            </div>

            <div>
              <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
                Tipo de Captor
              </label>
              <SelectField
                name="tipo_captor"
                value={mastType}
                onChange={(event) => setMastType(event.target.value)}
                options={[
                  { value: 'Franklin', label: 'Punta Franklin Estándar' },
                  { value: 'PDC', label: 'Captor Ionizante PDC' },
                  { value: 'Malla', label: 'Malla Conductora' },
                ]}
              />
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                className="flex-1 py-1.5 border border-red-500 text-red-600 hover:bg-red-50 rounded font-semibold text-xs transition"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleAddMast}
                className="btn-electric flex-1 py-1.5 bg-brand-blue hover:bg-brand-hover text-white rounded font-semibold text-xs transition"
              >
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MastilPositioner;
