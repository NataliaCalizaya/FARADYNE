// src/api/cobertura.js
// Usá el mismo cliente HTTP que en modelos3d.js / planos.js (baseURL incluye el prefijo global de la API).
import { apiClient } from './client';

export const coberturaApi = {
  /** GET /cobertura/proyecto/{idProyecto} -> CoberturaResponse */
  getCoberturaProyecto: async (idProyecto) => {
    const { data } = await apiClient.get(`/cobertura/proyecto/${idProyecto}`);
    return data;
  },
};
