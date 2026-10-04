from typing import Any, Dict, List, Optional

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

    @staticmethod
    def get_ng_by_localidad(db: Session, localidad: str) -> Optional[Dict[str, Any]]:
        """Busca la zona ceráunica cuya `ciudad` coincide EXACTAMENTE
        (case-insensitive) con `localidad`, y devuelve su Ng.

        A diferencia de `buscar_localidades` (que hace un prefijo para
        autocomplete), acá se busca una coincidencia exacta: es la localidad
        ya confirmada del proyecto, no texto parcial que el usuario está
        tipeando.
        """
        localidad = (localidad or "").strip()
        if not localidad:
            return None

        # Mismo escape de comodines que en buscar_localidades, por las dudas
        # de que la localidad tenga un % o _ literal (poco común, pero evita
        # que ilike los interprete como comodín).
        escapado = localidad.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

        stmt = select(ZonaCeraunica.id_zona, ZonaCeraunica.ciudad, ZonaCeraunica.ng).where(
            ZonaCeraunica.ciudad.ilike(escapado, escape="\\")
        )
        row = db.execute(stmt).first()
        if not row:
            return None

        return {"id_zona": row.id_zona, "ciudad": row.ciudad, "ng": float(row.ng)}