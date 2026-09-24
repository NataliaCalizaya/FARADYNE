import apiClient from './client';

/**
 * API del Modelo 2D / Planos (HU02).
 *
 * Convenciones:
 *  - Un "lado" de polígono es el índice de la arista i: va de puntos[i] a
 *    puntos[i + 1] (el último lado cierra con el primer punto).
 *  - Triángulos y rectángulos se CREAN con endpoints distintos, pero una vez
 *    creados son polígonos: se editan, se les agregan/quitan vértices y se
 *    eliminan con los mismos endpoints de /poligonos.
 */
export const planosApi = {
  // ==========================================================
  // PLANOS
  // ==========================================================

  /**
   * Sube un plano (DXF o PDF).
   * @param {File} file
   * @param {string} idProyecto
   */
  uploadPlano: async (file, idProyecto) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('idProyecto', idProyecto);

    const response = await apiClient.post('/planos', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });

    return response.data;
  },

  /**
   * Datos completos para dibujar el plano (líneas, capas, polígonos, niveles,
   * bounding_box, id_modelo2d y validado).
   * @param {string} id - ID del plano
   */
  getPlanoPreview: async (id) => {
    const response = await apiClient.get(`/planos/${id}/preview`);
    return response.data;
  },

  // ==========================================================
  // MODELO 2D
  // ==========================================================

  /**
   * Estado editable (poligonos, cotas_altura, capas, validado) sin las
   * líneas de fondo. Se pide después de cada operación de edición.
   * @param {string} idModelo2D
   */
  getModelo2DEdicion: async (idModelo2D, { incluirLineas = false } = {}) => {
    const response = await apiClient.get(`/modelos2d/${idModelo2D}/edicion`, {
      params: incluirLineas ? { incluir_lineas: true } : undefined,
    });
    return response.data;
  },

  /**
   * Actualización general (compatibilidad).
   * @param {string} id - ID del Modelo2D
   * @param {Object} data - { poligonos, lineas, capas, validado }
   */
  updateModelo2D: async (id, data) => {
    const response = await apiClient.patch(`/modelos2d/${id}`, data);
    return response.data;
  },

  validarModelo2D: async (idModelo2D) => {
    const response = await apiClient.post(`/modelos2d/${idModelo2D}/validar`);
    return response.data;
  },

  // ==========================================================
  // SUPERFICIES NUEVAS
  // ==========================================================

  /** payload: { puntos: [[x, y] x3], capa, page, tipo_cubierta } */
  createTriangulo: async (idModelo2D, payload) => {
    const response = await apiClient.post(
      `/modelos2d/${idModelo2D}/triangulos`,
      payload
    );
    return response.data;
  },

  /** payload: { x1, y1, x2, y2, capa, page, tipo_cubierta } */
  createRectangulo: async (idModelo2D, payload) => {
    const response = await apiClient.post(
      `/modelos2d/${idModelo2D}/rectangulos`,
      payload
    );
    return response.data;
  },

  // ==========================================================
  // POLÍGONOS (triángulos, rectángulos y reconocidos por igual)
  // ==========================================================

  /** data: { puntos: [{x, y}, ...] } */
  updatePoligono: async (idModelo2D, idPoligono, data) => {
    const response = await apiClient.patch(
      `/modelos2d/${idModelo2D}/poligonos/${idPoligono}`,
      data
    );
    return response.data;
  },

  deletePoligono: async (idModelo2D, idPoligono) => {
    const response = await apiClient.delete(
      `/modelos2d/${idModelo2D}/poligonos/${idPoligono}`
    );
    return response.data;
  },

  /**
   * Inserta un vértice. Sin `indice` va sobre el lado más cercano al punto.
   * data: { punto: {x, y}, indice?: number }
   */
  addVertice: async (idModelo2D, idPoligono, data) => {
    const response = await apiClient.post(
      `/modelos2d/${idModelo2D}/poligonos/${idPoligono}/vertices`,
      data
    );
    return response.data;
  },

  /** Elimina el vértice `indice` (el polígono conserva al menos 3). */
  removeVertice: async (idModelo2D, idPoligono, indice) => {
    const response = await apiClient.delete(
      `/modelos2d/${idModelo2D}/poligonos/${idPoligono}/vertices/${indice}`
    );
    return response.data;
  },

  // ==========================================================
  // NIVELES
  // ==========================================================

  /**
   * data: { valor, texto?, punto_seleccionado: {x, y}, page?, capa?,
   *         id_poligono?, lado?, asociar_automaticamente? }
   * Devuelve { mensaje, nivel }. `nivel.asociado` indica si quedó asociado a
   * un lado de polígono.
   */
  createNivel: async (idModelo2D, data) => {
    const response = await apiClient.post(
      `/modelos2d/${idModelo2D}/niveles`,
      data
    );
    return response.data;
  },

  /** data: { valor?, texto?, punto_seleccionado? } */
  updateNivel: async (idModelo2D, idNivel, data) => {
    const response = await apiClient.patch(
      `/modelos2d/${idModelo2D}/niveles/${idNivel}`,
      data
    );
    return response.data;
  },

  deleteNivel: async (idModelo2D, idNivel) => {
    const response = await apiClient.delete(
      `/modelos2d/${idModelo2D}/niveles/${idNivel}`
    );
    return response.data;
  },

  /**
   * Asocia un nivel (reconocido o creado a mano) a un lado del polígono.
   * Sin `lado` el backend usa el lado más cercano al nivel.
   */
  associateNivel: async (idModelo2D, idPoligono, idNivel, lado) => {
    const body =
      lado === undefined || lado === null ? {} : { lado: Number(lado) };

    const response = await apiClient.post(
      `/modelos2d/${idModelo2D}/poligonos/${idPoligono}/niveles/${idNivel}/asociar`,
      body
    );
    return response.data;
  },

  /** El nivel NO se borra: queda sin asociar. */
  disassociateNivel: async (idModelo2D, idPoligono, idNivel) => {
    const response = await apiClient.delete(
      `/modelos2d/${idModelo2D}/poligonos/${idPoligono}/niveles/${idNivel}/desasociar`
    );
    return response.data;
  },
};

export default planosApi;