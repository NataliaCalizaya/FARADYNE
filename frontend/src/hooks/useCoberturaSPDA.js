// src/hooks/useCoberturaSPDA.js
import { useEffect, useRef, useState } from 'react';
import { coberturaApi } from '../api/cobertura';

/**
 * Trae la cobertura SPDA del proyecto y la recalcula cada vez que cambian los
 * mástiles persistidos (alta, baja, movimiento o altura). Con debounce y
 * descartando respuestas viejas para que un arrastre no pise el resultado nuevo.
 */
export function useCoberturaSPDA(idProyecto, masts = [], { debounceMs = 400 } = {}) {
  const [coverage, setCoverage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const reqId = useRef(0);

  // Firma estable: solo cambia si cambia algo que afecta al cálculo.
  const firma = JSON.stringify(
    masts.map((m) => [m.id, m.posicion_x, m.posicion_y, m.posicion_z, m.altura])
  );

  useEffect(() => {
    if (!idProyecto) return undefined;
    const id = ++reqId.current;

    const t = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await coberturaApi.getCoberturaProyecto(idProyecto);
        if (id === reqId.current) {
          setCoverage(data);
          setError(null);
        }
      } catch (e) {
        if (id === reqId.current) setError(e);
      } finally {
        if (id === reqId.current) setLoading(false);
      }
    }, debounceMs);

    return () => clearTimeout(t);
  }, [idProyecto, firma, debounceMs]);

  return { coverage, loading, error };
}
