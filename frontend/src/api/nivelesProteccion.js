import apiClient from './client';

export const nivelesProteccionApi = {
  /**
   * HU04: Calculate SPDA lightning protection risk level
   * @param {Object} payload
   */
  calculateNivelProteccion: async (payload) => {
    const response = await apiClient.post('/niveles-proteccion', {
      id_proyecto: payload.id_proyecto,
      id_zona: payload.id_zona || null,
      departamento: payload.departamento || 'Lima',
      longitud_edificacion: payload.longitud_edificacion ? parseFloat(payload.longitud_edificacion) : null,
      anchura_edificacion: payload.anchura_edificacion ? parseFloat(payload.anchura_edificacion) : null,
      altura_edificacion: payload.altura_edificacion ? parseFloat(payload.altura_edificacion) : null,
      factor_ubicacion_cd: payload.factor_ubicacion_cd ? parseFloat(payload.factor_ubicacion_cd) : 1.0,
      factor_estructura_cb: payload.factor_estructura_cb ? parseFloat(payload.factor_estructura_cb) : 1.0,
      factor_contenido_cc: payload.factor_contenido_cc ? parseFloat(payload.factor_contenido_cc) : 1.0,
      factor_lineas_ce: payload.factor_lineas_ce ? parseFloat(payload.factor_lineas_ce) : 1.0,
    });
    return response.data;
  },

  /**
   * HU04: Retrieve previously calculated SPDA protection level
   * @param {string} idProyecto - Project UUID
   */
  getNivelProteccionByProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/niveles-proteccion/${idProyecto}`);
    return response.data;
  },
};

export default nivelesProteccionApi;
