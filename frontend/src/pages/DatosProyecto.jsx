import React, { useState } from 'react';
import { Info, FolderPlus, ArrowRight, CheckCircle2 } from 'lucide-react';

// TODO: conectar cuando exista el endpoint CRUD de Proyecto
export const DatosProyecto = ({ projectData, setProjectData, onNext }) => {
  const [formData, setFormData] = useState({
    nombre: projectData?.nombre || 'Centro Comercial ABC',
    cliente: projectData?.cliente || 'Constructora XYZ S.A.',
    region: projectData?.region || 'Buenos Aires',
    fecha: projectData?.fecha || new Date().toISOString().split('T')[0],
    proyectista: projectData?.proyectista || 'Ing. Juan García López',
    profesion: projectData?.profesion || 'Ingeniero Electricista',
  });

  const [saved, setSaved] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = (e) => {
    e.preventDefault();
    setProjectData((prev) => ({ ...prev, ...formData }));
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <h1 className="text-2xl font-bold font-condensed text-gray-900">
        Datos del Proyecto
      </h1>

      <div className="p-3 bg-blue-50 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 1 de 7:</strong> Registre los datos generales del proyecto y la ubicación geográfica.
        </div>
      </div>

      <form onSubmit={handleSave} className="bg-white border border-gray-200 rounded-md p-5 shadow-sm space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Nombre del Proyecto
            </label>
            <input
              type="text"
              name="nombre"
              value={formData.nombre}
              onChange={handleChange}
              placeholder="Ej: Centro comercial ABC"
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Cliente
            </label>
            <input
              type="text"
              name="cliente"
              value={formData.cliente}
              onChange={handleChange}
              placeholder="Nombre del cliente"
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Provincia / Región
            </label>
            <select
              name="region"
              value={formData.region}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            >
              <option value="Buenos Aires">Buenos Aires</option>
              <option value="CABA">CABA</option>
              <option value="Córdoba">Córdoba</option>
              <option value="Santa Fe">Santa Fe</option>
              <option value="Mendoza">Mendoza</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Fecha del Proyecto
            </label>
            <input
              type="date"
              name="fecha"
              value={formData.fecha}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Nombre y Apellido del Proyectista
            </label>
            <input
              type="text"
              name="proyectista"
              value={formData.proyectista}
              onChange={handleChange}
              placeholder="Ej: Juan García López"
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-bold text-gray-600 uppercase mb-1">
              Profesión
            </label>
            <select
              name="profesion"
              value={formData.profesion}
              onChange={handleChange}
              className="w-full p-2 border border-gray-300 rounded text-xs focus:border-brand-blue focus:outline-none"
            >
              <option value="Ingeniero Electricista">Ingeniero Electricista</option>
              <option value="Ingeniero en Sistemas">Ingeniero en Sistemas</option>
              <option value="Técnico Electricista">Técnico Electricista</option>
            </select>
          </div>
        </div>

        {saved && (
          <div className="p-2 bg-emerald-50 text-emerald-800 text-xs rounded border border-emerald-200 flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Datos guardados en la sesión del proyecto.
          </div>
        )}

        <div className="flex justify-between items-center pt-2 border-t border-gray-100">
          <button
            type="submit"
            className="px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition"
          >
            Guardar Proyecto
          </button>
          <button
            type="button"
            onClick={onNext}
            className="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold rounded text-xs flex items-center gap-1 transition"
          >
            Siguiente <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </form>
    </div>
  );
};

export default DatosProyecto;
