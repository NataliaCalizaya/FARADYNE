import apiClient from './client';

export const proyectosApi = {
  /**
   * HU04: Obtiene nombre y ubicación del proyecto, para mostrarla junto al
   * Ng adoptado en el Paso 1 del cálculo de Nivel de Protección.
   * @param {string} idProyecto - Project UUID/ID
   */
  obtenerUbicacionProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/proyectos/${idProyecto}/ubicacion`);
    return response.data;
  },
};

export default proyectosApi;