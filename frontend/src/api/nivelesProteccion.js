import apiClient from './client';

/**
 * Nota sobre el Ng: el backend lo obtiene haciendo coincidir la `localidad`
 * del proyecto con `zona_ceraunica.ciudad` (o usando `id_zona` si se envía).
 * Si no hay coincidencia responde 422 con un `detail` en texto: mostrarlo con
 * getApiErrorMessage(error) de ./apiErrors.
 */
export const nivelesProteccionApi = {
  /**
   * HU04: Calcula (sin guardar) Ae, Nd, Nc y el nivel de protección
   * recomendado según el Anexo A/B/E/F. Se usa para previsualizar el
   * resultado cada vez que el usuario cambia los factores A-B-C-D-E.
   * @param {Object} payload
   * @param {number|string} payload.id_proyecto
   * @param {number|string} [payload.id_zona] - opcional; si no, se resuelve por localidad
   * @param {number|string} payload.factor_a
   * @param {number|string} payload.factor_b
   * @param {number|string} payload.factor_c
   * @param {number|string} payload.factor_d
   * @param {number|string} payload.factor_e
   */
  calcularNivelProteccion: async (payload) => {
    const response = await apiClient.post('/niveles-proteccion/calcular', {
      id_proyecto: String(payload.id_proyecto),
      id_zona: payload.id_zona || null,
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
   * usuario haya elegido libremente en la grilla (nivel_seleccionado:
   * 'I' | 'II' | 'III' | 'IV'). Si no se envía, se guarda el recomendado.
   * @param {Object} payload - mismos campos que calcularNivelProteccion, más nivel_seleccionado
   */
  guardarNivelProteccion: async (payload) => {
    const response = await apiClient.post('/niveles-proteccion', {
      id_proyecto: String(payload.id_proyecto),
      id_zona: payload.id_zona || null,
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
   * HU04: Obtiene el nivel de protección ya calculado de un proyecto
   * (404 si todavía no se calculó).
   * @param {number|string} idProyecto - ID del proyecto
   */
  getNivelProteccionByProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/niveles-proteccion/${idProyecto}`);
    return response.data;
  },
};

export default nivelesProteccionApi;
