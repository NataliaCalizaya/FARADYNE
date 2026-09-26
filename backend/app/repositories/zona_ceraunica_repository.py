from typing import List
from app.core.database import fetch_all


class ZonaCeraunicaRepository:

    @staticmethod
    def buscar_localidades(query: str, limit: int = 10) -> List[str]:
        """Autocomplete de localidades: devuelve valores de
        `zona_ceraunica.ciudad` que EMPIEZAN con `query` (case-insensitive),
        sin duplicados, ordenados alfabéticamente.

        Ej: buscar_localidades("m") -> ["Maimará", "Monterrico", ...]

        Usa el prefijo 'query%' (no '%query%') a propósito: para un campo de
        localidad tiene más sentido "empieza con" que "contiene en cualquier
        parte", que traería resultados poco intuitivos.
        """
        query = (query or "").strip()
        if not query:
            return []

        sql = """
            SELECT DISTINCT ciudad
            FROM zona_ceraunica
            WHERE ciudad ILIKE %s
            ORDER BY ciudad ASC
            LIMIT %s;
        """
        pattern = f"{query}%"
        rows = fetch_all(sql, (pattern, limit)) or []
        return [r["ciudad"] for r in rows if r.get("ciudad")]
