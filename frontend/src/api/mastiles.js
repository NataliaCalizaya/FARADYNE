import apiClient from './client';

/**
 * API de Mástiles Captores (HU05).
 *
 * El backend acepta `id_modelo3d` directo o `id_modelo2d` (el endpoint
 * resuelve el modelo 3D asociado automáticamente). Todos los IDs son enteros
 * (se pueden pasar como número o string numérico).
 */
export const mastilesApi = {
  /**
   * Crea un mástil captor.
   * @param {Object} payload
   * @param {number|string} [payload.id_modelo3d] - ID del modelo 3D (o usar id_modelo2d)
   * @param {number|string} [payload.id_modelo2d] - ID del modelo 2D (alternativa)
   * @param {number} payload.posicion_x
   * @param {number} payload.posicion_y
   * @param {number} [payload.posicion_z] - si es 0 / no viene, el backend lo
   *   resuelve con la altura del polígono bajo el punto
   * @param {number} payload.altura
   * @param {string} [payload.tipo] - por defecto 'Franklin'
   */
  createMastil: async (payload) => {
    const response = await apiClient.post('/mastiles', {
      id_modelo3d: payload.id_modelo3d ? String(payload.id_modelo3d) : undefined,
      id_modelo2d: payload.id_modelo2d ? String(payload.id_modelo2d) : undefined,
      posicion_x: parseFloat(payload.posicion_x),
      posicion_y: parseFloat(payload.posicion_y),
      posicion_z: parseFloat(payload.posicion_z ?? 0.0),
      altura: parseFloat(payload.altura),
      tipo: payload.tipo || 'Franklin',
    });
    return response.data;
  },

  /**
   * Actualiza posición, altura o tipo de un mástil.
   * @param {number|string} id - ID del mástil
   * @param {Object} payload
   */
  updateMastil: async (id, payload) => {
    const response = await apiClient.put(`/mastiles/${id}`, {
      posicion_x: payload.posicion_x !== undefined ? parseFloat(payload.posicion_x) : undefined,
      posicion_y: payload.posicion_y !== undefined ? parseFloat(payload.posicion_y) : undefined,
      posicion_z: payload.posicion_z !== undefined ? parseFloat(payload.posicion_z) : undefined,
      altura: payload.altura !== undefined ? parseFloat(payload.altura) : undefined,
      tipo: payload.tipo || undefined,
    });
    return response.data;
  },

  /**
   * Elimina un mástil. 404 si no existe.
   * @param {number|string} id - ID del mástil
   */
  deleteMastil: async (id) => {
    const response = await apiClient.delete(`/mastiles/${id}`);
    return response.data;
  },

  /**
   * Obtiene todos los mástiles de un Modelo 3D.
   * Devuelve [] si el ID es inválido o el modelo no existe.
   * @param {number|string} idModelo3D
   */
  getMastilesByModelo3D: async (idModelo3D) => {
    const response = await apiClient.get(`/mastiles/modelo3d/${idModelo3D}`);
    return response.data;
  },

  /**
   * Obtiene todos los mástiles asociados a un Modelo 2D.
   * @param {number|string} idModelo2D
   */
  getMastilesByModelo2D: async (idModelo2D) => {
    const response = await apiClient.get(`/mastiles/modelo2d/${idModelo2D}`);
    return response.data;
  },

  /**
   * Evalúa la cobertura SPDA de todos los mástiles del proyecto (no guarda).
   * El radio de la esfera sale del nivel de protección guardado (HU04).
   * @param {number|string} idProyecto
   */
  getCobertura: async (idProyecto) => {
    const response = await apiClient.get(`/cobertura/proyecto/${idProyecto}`);
    return response.data;
  },

  /**
   * Recalcula la cobertura y la guarda en `resultado_simulacion`.
   * @param {number|string} idProyecto
   */
  guardarCobertura: async (idProyecto) => {
    const { data } = await apiClient.post(`/cobertura/proyecto/${idProyecto}/guardar`);
    return data;
  },
};

export default mastilesApi;
