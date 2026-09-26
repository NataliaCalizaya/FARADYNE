// Ajustar este import al mismo cliente axios/fetch que usan el resto de
// los módulos de /api (ej. planos.js, mastiles.js). Si por ejemplo el
// patrón real es `import { apiClient } from './apiClient';` o similar,
// reemplazar la línea de abajo por ese import y usar apiClient en vez de
// apiClient default.
import apiClient from './client';

export const zonaCeraunicaApi = {
  /**
   * Devuelve un array de strings (nombres de ciudad) que empiezan con `q`.
   * Si `q` está vacío, devuelve [] sin llamar al backend.
   */
  buscarLocalidades: async (q) => {
    const query = (q || '').trim();
    if (!query) return [];
    const { data } = await apiClient.get('/zonas-ceraunicas/localidades', {
      params: { q: query },
    });
    return data;
  },
};

export default zonaCeraunicaApi;
