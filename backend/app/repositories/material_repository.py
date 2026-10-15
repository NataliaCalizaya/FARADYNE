from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.material_catalogo import MaterialCatalogo


class MaterialRepository:

    @staticmethod
    def get_codigos(db: Session) -> Dict[Tuple[str, Optional[float]], Optional[str]]:
        """Devuelve {(clave, altura|None): codigo} de todo el catálogo."""
        rows = db.scalars(select(MaterialCatalogo)).all()
        return {
            (r.clave, round(r.altura, 2) if r.altura is not None else None): r.codigo
            for r in rows
        }