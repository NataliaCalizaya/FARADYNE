import axios from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:6500/api/v1';

export const TOKEN_KEY = 'faradyne_token';
export const USER_KEY = 'faradyne_usuario';

export const apiClient = axios.create({
  baseURL,
  headers: {
    'Accept': 'application/json',
  },
});

// Agrega el token JWT a cada request
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Si el token venció o es inválido (401), cierra la sesión y vuelve al login
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const esLogin = error.config?.url?.includes('/auth/login');
    if (error.response?.status === 401 && !esLogin) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

export default apiClient;