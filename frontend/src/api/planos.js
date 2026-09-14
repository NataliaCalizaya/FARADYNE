import apiClient from './client';

export const planosApi = {
  /**
   * HU02: Upload architectural drawing (DXF or PDF)
   * @param {File} file - DXF or PDF file
   * @param {string} idProyecto - Associated project UUID
   */
  uploadPlano: async (file, idProyecto) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('idProyecto', idProyecto);

    const response = await apiClient.post('/planos', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  /**
   * HU02: Get preview data for drawing
   * @param {string} id - Plano UUID
   */
  getPlanoPreview: async (id) => {
    const response = await apiClient.get(`/planos/${id}/preview`);
    return response.data;
  },

  /**
   * HU02: Update 2D geometry / validation status
   * @param {string} id - Modelo2D ID
   * @param {Object} data - { poligonos, lineas, capas, validado }
   */
  updateModelo2D: async (id, data) => {
    const response = await apiClient.patch(`/modelos2d/${id}`, data);
    return response.data;
  },
};


export default planosApi;
