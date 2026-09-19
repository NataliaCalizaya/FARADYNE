import apiClient from './client';

export const mastilesApi = {
  /**
   * HU05: Add an air terminal mast to 3D model
   * @param {Object} payload
   */
  createMastil: async (payload) => {
    const response = await apiClient.post('/mastiles', {
      id_modelo3d: payload.id_modelo3d,
      id_proyecto: payload.id_proyecto,
      posicion_x: parseFloat(payload.posicion_x),
      posicion_y: parseFloat(payload.posicion_y),
      posicion_z: parseFloat(payload.posicion_z || 0.0),
      altura: parseFloat(payload.altura),
      tipo: payload.tipo || 'Franklin',
    });
    return response.data;
  },

  /**
   * HU05: Move or update an air terminal mast
   * @param {string} id - Mast UUID
   * @param {Object} payload
   */
  updateMastil: async (id, payload) => {
    const response = await apiClient.put(`/mastiles/${id}`, {
      posicion_x: parseFloat(payload.posicion_x),
      posicion_y: parseFloat(payload.posicion_y),
      posicion_z: parseFloat(payload.posicion_z || 0.0),
      altura: parseFloat(payload.altura),
      tipo: payload.tipo || 'Franklin',
    });
    return response.data;
  },

  /**
   * HU05: Delete a mast
   * @param {string} id - Mast UUID
   */
  deleteMastil: async (id) => {
    const response = await apiClient.delete(`/mastiles/${id}`);
    return response.data;
  },

  /**
   * HU05: Evaluate SPDA protection coverage for all placed masts in a project
   * @param {string} idProyecto - Project UUID
   */
  getCobertura: async (idProyecto) => {
    const response = await apiClient.get(`/mastiles/proyecto/${idProyecto}/cobertura`);
    return response.data;
  },
};

export default mastilesApi;
