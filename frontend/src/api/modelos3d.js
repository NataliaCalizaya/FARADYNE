import apiClient from './client';

export const modelos3dApi = {
  /**
   * HU03: Trigger deterministic programmatic 3D volumetric extrusion from 2D model ID
   * @param {string} idModelo2d - Modelo 2D UUID
   */
  // createModelo3D: async (idModelo2d) => {
  //   const response = await apiClient.post('/modelos3d', {
  //     id_modelo2d: idModelo2d,
  //   });
  //   return response.data;
  // },

  /**
   * HU03: Retrieve generated 3D geometry for model viewer
   * @param {string} id - Modelo 3D UUID
   */
  getModelo3D: async (id) => {
    const response = await apiClient.get(`/modelos3d/${id}`);
    return response.data;
  },

  generateModelo3D: async (data) => {
    const response = await apiClient.post('/modelos3d', data);
    return response.data;
  },
    
  /**
   * HU03: Reset 3D camera view settings
   * @param {string} id - Modelo 3D UUID
   * @param {number[]} camera - [x, y, z] camera coords
   * @param {number[]} target - [x, y, z] focus coords
   */
  resetView: async (id, camera = [50, 50, 50], target = [0, 0, 0]) => {
    const response = await apiClient.patch(`/modelos3d/${id}/reset-view`, {
      camera,
      target,
    });
    return response.data;
  },
  // Obtiene un modelo 3D ya generado


  // Resetea la cámara
  resetView: async (idModelo3D, payload = {}) => {
    const response = await apiClient.patch(`/modelos3d/${idModelo3D}/reset-view`, payload);
    return response.data;
  }
};

export default modelos3dApi;
