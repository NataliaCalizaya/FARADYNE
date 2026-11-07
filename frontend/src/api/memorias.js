import apiClient from './client';

export const memoriasApi = {
  generar: async (idProyecto, payload = {}) =>
    (await apiClient.post(`/memorias/proyecto/${idProyecto}/generar`, payload)).data,

  obtener: async (idProyecto) =>
    (await apiClient.get(`/memorias/proyecto/${idProyecto}`)).data,

  descargar: async (idProyecto) =>
    (await apiClient.get(`/memorias/proyecto/${idProyecto}/descargar`, { responseType: 'blob' })).data,

  vistaPrevia: async (idProyecto) =>
    (await apiClient.get(`/memorias/proyecto/${idProyecto}/vista-previa`)).data,
};

export default memoriasApi;
