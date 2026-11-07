import apiClient from './client';

export const materialesApi = {
  /**
   * Listado de materiales de un proyecto, computado a partir de los mástiles guardados.
   * @param {number|string} idProyecto - ID del proyecto
   * @returns {Promise<{id_proyecto: string, total_mastiles: number, items: Array}>}
   */
  getListadoMateriales: async (idProyecto) => {
    try {
      const response = await apiClient.get(`/materiales/proyecto/${idProyecto}`);
      return response.data;
    } catch (error) {
      const detail = error.response?.data?.detail;
      throw new Error(
        typeof detail === 'string' ? detail : 'No se pudo obtener el listado de materiales.'
      );
    }
  },
};

export const getListadoMateriales = materialesApi.getListadoMateriales;

export default materialesApi;