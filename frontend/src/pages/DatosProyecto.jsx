import React, { useState } from 'react';
import {
  Info,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Building2,
  MapPin,
  Calendar,
  UserCog,
  FileText,
  Map
} from 'lucide-react';
import { proyectosApi } from '../api/proyectos';

export const DatosProyecto = ({ projectData, setProjectData, idProyecto, onProyectoCreado, onNext }) => {
  const [formData, setFormData] = useState({
    nombre: projectData?.nombre || '',
    cliente: projectData?.cliente || '',
    descripcion: projectData?.descripcion || '',
    ubicacion: projectData?.ubicacion || '',
    provincia: projectData?.provincia || '',
    departamento: projectData?.departamento || '',
    localidad: projectData?.localidad || '',
    fecha_del_proyecto: projectData?.fecha_del_proyecto || new Date().toISOString().split('T')[0],
  });

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!formData.nombre.trim()) {
      setError('El nombre del proyecto es obligatorio.');
      return;
    }
    setSaving(true);
    setError(null);

    try {
      let proyecto;
      const payload = {
        nombre: formData.nombre,
        cliente: formData.cliente || null,
        descripcion: formData.descripcion || null,
        ubicacion: formData.ubicacion || null,
        provincia: formData.provincia || null,
        departamento: formData.departamento || null,
        localidad: formData.localidad || null,
        fecha_del_proyecto: formData.fecha_del_proyecto || null,
      };

      if (idProyecto) {
        proyecto = await proyectosApi.actualizarProyecto(idProyecto, payload);
      } else {
        proyecto = await proyectosApi.crearProyecto(payload);
      }

      setProjectData((prev) => ({ ...prev, ...formData, nombre: proyecto.nombre }));

      if (onProyectoCreado) {
        onProyectoCreado(proyecto.id_proyecto, proyecto);
      }

      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Error al guardar proyecto:', err);
      const msg = err.response?.data?.detail || 'Error al guardar el proyecto en el servidor.';
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <h1 className="workflow-title project-data-title text-2xl font-bold font-condensed text-gray-900">
        Datos del Proyecto
      </h1>

      <div className="workflow-notice project-data-notice p-3 bg-blue-50/95 border border-blue-200 text-brand-blue rounded-md flex items-center gap-2 text-xs">
        <Info className="w-4 h-4 shrink-0" />
        <div>
          <strong>Paso 1 de 7:</strong> Registre los datos generales del proyecto y la ubicación
          geográfica. Al guardar se crea (o actualiza) el registro real en la base de datos y se
          obtiene el ID del proyecto.
        </div>
      </div>

      {idProyecto && (
        <div className="p-2 bg-slate-50 border border-slate-200 text-slate-600 rounded text-[11px] font-mono">
          ID de proyecto: <span className="text-brand-blue font-semibold">{idProyecto}</span>
        </div>
      )}

      <form
        onSubmit={handleSave}
        className="project-data-card card-hover bg-white/90 border border-gray-200 rounded-md p-5 shadow-sm space-y-4"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div className="project-field">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <Building2 className="w-3.5 h-3.5 text-brand-blue" />
              Nombre del Proyecto <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="nombre"
              value={formData.nombre}
              onChange={handleChange}
              placeholder="Ej: Centro comercial ABC"
              required
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <UserCog className="w-3.5 h-3.5 text-brand-blue" />
              Cliente
            </label>
            <input
              type="text"
              name="cliente"
              value={formData.cliente}
              onChange={handleChange}
              placeholder="Nombre del cliente o empresa"
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <Calendar className="w-3.5 h-3.5 text-brand-blue" />
              Fecha del Proyecto
            </label>
            <input
              type="date"
              name="fecha_del_proyecto"
              value={formData.fecha_del_proyecto}
              onChange={handleChange}
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <Map className="w-3.5 h-3.5 text-brand-blue" />
              Provincia
            </label>
            <input
              type="text"
              name="provincia"
              value={formData.provincia}
              onChange={handleChange}
              placeholder="Ej: Jujuy"
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <MapPin className="w-3.5 h-3.5 text-brand-blue" />
              Departamento
            </label>
            <input
              type="text"
              name="departamento"
              value={formData.departamento}
              onChange={handleChange}
              placeholder="Ej: Dr. Manuel Belgrano"
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <MapPin className="w-3.5 h-3.5 text-brand-blue" />
              Localidad
            </label>
            <input
              type="text"
              name="localidad"
              value={formData.localidad}
              onChange={handleChange}
              placeholder="Ej: San Salvador de Jujuy"
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field md:col-span-2">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <MapPin className="w-3.5 h-3.5 text-brand-blue" />
              Ubicación / Dirección exacta
            </label>
            <input
              type="text"
              name="ubicacion"
              value={formData.ubicacion}
              onChange={handleChange}
              placeholder="Ej: Av. Siempre Viva 742"
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>

          <div className="project-field md:col-span-3">
            <label className="flex items-center gap-1.5 text-[11px] font-bold text-gray-600 uppercase mb-1">
              <FileText className="w-3.5 h-3.5 text-brand-blue" />
              Descripción
            </label>
            <input
              type="text"
              name="descripcion"
              value={formData.descripcion}
              onChange={handleChange}
              placeholder="Breve descripción del proyecto"
              className="input-electric w-full p-2 border border-gray-300 rounded text-xs"
            />
          </div>
        </div>

        {error && (
          <div className="animate-fade-in p-2 bg-red-50 text-red-700 text-xs rounded border border-red-200 flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4 text-red-500 shrink-0" /> {error}
          </div>
        )}

        {saved && (
          <div className="animate-fade-in p-2 bg-emerald-50 text-emerald-800 text-xs rounded border border-emerald-200 flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" /> Proyecto guardado en la base de datos.
          </div>
        )}

        <div className="flex justify-between items-center pt-2 border-t border-gray-100">
          <button
            type="submit"
            disabled={saving}
            className="btn-electric px-4 py-2 bg-brand-blue hover:bg-brand-hover text-white font-bold rounded text-xs transition flex items-center gap-1.5 disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" /> Guardando...
              </>
            ) : (
              <>{idProyecto ? 'Actualizar Proyecto' : 'Crear Proyecto'}</>
            )}
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={!idProyecto}
            className="btn-electric px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold rounded text-xs flex items-center gap-1 transition disabled:opacity-40 disabled:cursor-not-allowed"
            title={!idProyecto ? 'Primero guardá el proyecto' : undefined}
          >
            Siguiente <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </form>
    </div>
  );
};

export default DatosProyecto;