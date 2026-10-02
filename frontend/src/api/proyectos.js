import apiClient from './client';

export const proyectosApi = {
  /**
   * Lista todos los proyectos (más recientes primero).
   */
  listarProyectos: async () => {
    const response = await apiClient.get('/proyectos');
    return response.data;
  },

  /**
   * Crea un nuevo proyecto en la base de datos.
   * `cliente` y `ubicacion` son obligatorios (422 si faltan). `localidad` es
   * la que se usa para resolver el Ng de la zona ceráunica en HU04.
   * @param {Object} payload
   * @param {string} payload.nombre
   * @param {string} payload.cliente
   * @param {string} payload.ubicacion
   * @param {string} [payload.descripcion]
   * @param {string} [payload.departamento]
   * @param {string} [payload.provincia]
   * @param {string} [payload.localidad]
   * @param {string} [payload.fecha_del_proyecto] - 'YYYY-MM-DD'
   * @param {string} [payload.estado] - por defecto 'borrador'
   * @returns {Object} El proyecto creado; su ID viene en el campo `id_proyecto`
   */
  crearProyecto: async (payload) => {
    const response = await apiClient.post('/proyectos', payload);
    return response.data;
  },

  /**
   * Obtiene un proyecto por su ID.
   * @param {number|string} idProyecto - ID del proyecto
   */
  obtenerProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/proyectos/${idProyecto}`);
    return response.data;
  },

  /**
   * Obtiene el proyecto con IDs derivados resueltos (id_plano, id_modelo2d,
   * id_modelo3d, geometria_validada) para reconstruir el estado al abrir
   * una URL directa (F5 o enlace compartido con colaboradores).
   * @param {number|string} idProyecto - ID del proyecto
   */
  getProyectoCompleto: async (idProyecto) => {
    const response = await apiClient.get(`/proyectos/${idProyecto}/completo`);
    return response.data;
  },

  /**
   * Actualiza los datos de un proyecto existente (404 si no existe).
   * @param {number|string} idProyecto - ID del proyecto
   * @param {Object} payload - campos a actualizar
   */
  actualizarProyecto: async (idProyecto, payload) => {
    const response = await apiClient.patch(`/proyectos/${idProyecto}`, payload);
    return response.data;
  },

  /**
   * HU04: Obtiene { id_proyecto, nombre, localidad } del proyecto, para
   * mostrar la localidad junto al Ng adoptado en el Paso 1 del cálculo de
   * Nivel de Protección.
   * @param {number|string} idProyecto - ID del proyecto
   */
  obtenerUbicacionProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/proyectos/${idProyecto}/ubicacion`);
    return response.data;
  },
};

export default proyectosApi;
