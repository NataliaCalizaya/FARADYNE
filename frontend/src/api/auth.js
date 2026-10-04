import apiClient from './client';

export const authApi = {
    /**
     * Inicia sesión. Devuelve { access_token, token_type, usuario }.
     */
    login: async (email, password) => {
        const response = await apiClient.post('/auth/login', { email, password });
        return response.data;
    },

    /**
     * Crea un usuario nuevo. Devuelve { id_usuario, nombre, email, fecha_creacion }.
     */
    registro: async ({ nombre, email, password }) => {
        const response = await apiClient.post('/auth/registro', { nombre, email, password });
        return response.data;
    },

    /**
     * Devuelve el usuario logueado (requiere token).
     */
    me: async () => {
        const response = await apiClient.get('/auth/me');
        return response.data;
    },
};

export default authApi;