import apiClient from './client';

export const proyectosApi = {
  /**
   * Lista todos los proyectos.
   */
  listarProyectos: async () => {
    const response = await apiClient.get('/proyectos');
    return response.data;
  },

  /**
   * Crea un nuevo proyecto en la base de datos.
   * @param {Object} payload - { nombre, descripcion, ubicacion, departamento, provincia, distrito, estado }
   * @returns {Object} El proyecto creado con su UUID (campo 'id')
   */
  crearProyecto: async (payload) => {
    const response = await apiClient.post('/proyectos', payload);
    return response.data;
  },

  /**
   * Obtiene un proyecto por su ID.
   * @param {string} idProyecto - UUID del proyecto
   */
  obtenerProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/proyectos/${idProyecto}`);
    return response.data;
  },

  /**
   * Actualiza los datos de un proyecto existente.
   * @param {string} idProyecto - UUID del proyecto
   * @param {Object} payload - campos a actualizar
   */
  actualizarProyecto: async (idProyecto, payload) => {
    const response = await apiClient.patch(`/proyectos/${idProyecto}`, payload);
    return response.data;
  },

  /**
   * HU04: Obtiene nombre y ubicación del proyecto, para mostrarla junto al
   * Ng adoptado en el Paso 1 del cálculo de Nivel de Protección.
   * @param {string} idProyecto - Project UUID
   */
  obtenerUbicacionProyecto: async (idProyecto) => {
    const response = await apiClient.get(`/proyectos/${idProyecto}/ubicacion`);
    return response.data;
  },
};

export default proyectosApi;