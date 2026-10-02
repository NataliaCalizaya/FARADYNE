/**
 * Convierte el error de axios en un texto listo para mostrar al usuario.
 *
 * El backend (FastAPI) responde `detail` de dos formas:
 *  - string: errores de negocio (404, 400, 422 propios, ej. "La localidad del
 *    proyecto no coincide con ninguna zona ceráunica...").
 *  - array de objetos { loc, msg, type }: errores de validación automática
 *    (ej. un id que no es numérico). Mostrarlo tal cual da "[object Object]".
 *
 * Uso:
 *   try { await nivelesProteccionApi.calcularNivelProteccion(p); }
 *   catch (error) { setError(getApiErrorMessage(error)); }
 *
 * @param {unknown} error - error capturado en el catch
 * @param {string} [fallback] - texto si no se puede extraer nada más útil
 * @returns {string}
 */
export function getApiErrorMessage(
  error,
  fallback = 'Ocurrió un error inesperado.'
) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => {
        const campo = Array.isArray(item?.loc)
          ? item.loc.filter((p) => !['body', 'path', 'query'].includes(p)).join('.')
          : '';
        const mensaje = item?.msg || 'valor inválido';
        return campo ? `${campo}: ${mensaje}` : mensaje;
      })
      .join(' · ');
  }

  if (detail && typeof detail === 'object' && typeof detail.message === 'string') {
    return detail.message;
  }

  // Sin respuesta del servidor (caído, CORS, sin red).
  if (error?.request && !error?.response) {
    return 'No se pudo conectar con el servidor.';
  }

  return error?.message || fallback;
}

export default getApiErrorMessage;
