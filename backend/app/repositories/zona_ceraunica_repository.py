from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.zona_ceraunica import ZonaCeraunica


class ZonaCeraunicaRepository:

    @staticmethod
    def buscar_localidades(db: Session, query: str, limit: int = 10) -> List[str]:
        """Autocomplete de localidades: devuelve valores de
        `zona_ceraunica.ciudad` que EMPIEZAN con `query` (case-insensitive),
        sin duplicados, ordenados alfabéticamente.

        Ej: buscar_localidades(db, "m") -> ["Maimará", "Monterrico", ...]

        Usa el prefijo 'query%' (no '%query%') a propósito: para un campo de
        localidad tiene más sentido "empieza con" que "contiene en cualquier
        parte". Los comodines % y _ escritos por el usuario se escapan.
        """
        query = (query or "").strip()
        if not query:
            return []

        escapado = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        stmt = (
            select(ZonaCeraunica.ciudad)
            .where(ZonaCeraunica.ciudad.ilike(f"{escapado}%", escape="\\"))
            .distinct()
            .order_by(ZonaCeraunica.ciudad.asc())
            .limit(limit)
        )
        return [ciudad for ciudad in db.scalars(stmt).all() if ciudad]
