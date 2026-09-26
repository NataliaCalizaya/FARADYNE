import apiClient from './client';

export const nivelesProteccionApi = {
  /**
   * HU04: Calcula (sin guardar) Ae, Nd, Nc y el nivel de protección
   * recomendado según el Anexo A/B/E/F. Se usa para previsualizar el
   * resultado cada vez que el usuario cambia los factores A-B-C-D-E.
   * @param {Object} payload
   */
  calcularNivelProteccion: async (payload) => {
    const response = await apiClient.post('/niveles-proteccion/calcular', {
      id_proyecto: String(payload.id_proyecto),
      id_zona: payload.id_zona || null,
      departamento: payload.departamento || null,
      factor_a: parseFloat(payload.factor_a),
      factor_b: parseFloat(payload.factor_b),
      factor_c: parseFloat(payload.factor_c),
      factor_d: parseFloat(payload.factor_d),
      factor_e: parseFloat(payload.factor_e),
    });
    return response.data;
  },

  /**
   * HU04: Persiste el Nivel de Protección, respetando el nivel que el
   * usuario haya elegido libremente en la grilla (nivel_seleccionado).
   * @param {Object} payload
   */
  guardarNivelProteccion: async (payload) => {
    const response = await apiClient.post('/niveles-proteccion', {
      id_proyecto: String(payload.id_proyecto),
      id_zona: payload.id_zona || null,
      departamento: payload.departamento || null,
      factor_a: parseFloat(payload.factor_a),
      factor_b: parseFloat(payload.factor_b),
      factor_c: parseFloat(payload.factor_c),
      factor_d: parseFloat(payload.factor_d),
      factor_e: parseFloat(payload.factor_e),
      nivel_seleccionado: payload.nivel_seleccionado || null,
    });
    return response.data;
  },

  /**
   * HU04: Retrieve previously calculated SPDA protection level
   * @param {string} idProyecto - Project UUID
   */
  getNivelProteccionByProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/niveles-proteccion/${idProyecto}`);
    return response.data;
  },
};

export default nivelesProteccionApi;