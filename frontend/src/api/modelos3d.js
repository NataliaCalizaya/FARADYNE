import apiClient from './client';

export const modelos3dApi = {
  /**
   * HU03: Genera (o actualiza) el Modelo 3D a partir del Modelo 2D.
   * @param {Object} data - { id_modelo2d: string }
   */
  generateModelo3D: async (data) => {
    const response = await apiClient.post('/modelos3d', data);
    return response.data;
  },

  /**
   * HU03: Obtiene un Modelo 3D por su ID.
   * @param {string} id - UUID del Modelo 3D
   */
  getModelo3D: async (id) => {
    const response = await apiClient.get(`/modelos3d/${id}`);
    return response.data;
  },

  /**
   * Busca el Modelo 3D asociado a un Modelo 2D.
   * @param {string} idModelo2D - UUID del Modelo 2D
   */
  getModelo3DByModelo2D: async (idModelo2D) => {
    const response = await apiClient.get(`/modelos3d/by-modelo2d/${idModelo2D}`);
    return response.data;
  },

  /**
   * HU03: Resetea la posición de cámara del visor 3D.
   * @param {string} id - UUID del Modelo 3D
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
