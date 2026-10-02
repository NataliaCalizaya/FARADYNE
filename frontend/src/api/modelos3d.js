import apiClient from './client';

export const modelos3dApi = {
  /**
   * HU03: Genera (o regenera) el Modelo 3D a partir del Modelo 2D.
   * Requiere que el Modelo 2D esté validado (400 si no lo está; cualquier
   * edición posterior del 2D lo deja sin validar de nuevo).
   * @param {Object} data - { id_modelo2d: number|string }
   */
  generateModelo3D: async (data) => {
    const response = await apiClient.post('/modelos3d', data);
    return response.data;
  },

  /**
   * HU03: Obtiene un Modelo 3D por su ID.
   * @param {number|string} id - ID del Modelo 3D
   */
  getModelo3D: async (id) => {
    const response = await apiClient.get(`/modelos3d/${id}`);
    return response.data;
  },

  /**
   * Busca el Modelo 3D asociado a un Modelo 2D (404 si todavía no se generó).
   * @param {number|string} idModelo2D - ID del Modelo 2D
   */
  getModelo3DByModelo2D: async (idModelo2D) => {
    const response = await apiClient.get(`/modelos3d/by-modelo2d/${idModelo2D}`);
    return response.data;
  },

  /**
   * HU03: Resetea la posición de cámara del visor 3D.
   * @param {number|string} id - ID del Modelo 3D
   * @param {number[]} camera - [x, y, z]
   * @param {number[]} target - [x, y, z]
   */
  resetView: async (id, camera = [50, 50, 50], target = [0, 0, 0]) => {
    const response = await apiClient.patch(`/modelos3d/${id}/reset-view`, {
      camera,
      target,
    });
    return response.data;
  },
};

export default modelos3dApi;
