from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memoria_descriptiva import MemoriaDescriptiva
from app.repositories.utils import commit_or_rollback, to_dict


class MemoriaDescriptivaRepository:
    @staticmethod
    def get_por_proyecto(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        return to_dict(db.scalars(select(MemoriaDescriptiva).where(MemoriaDescriptiva.id_proyecto == id_proyecto)).first())

    @staticmethod
    def upsert(db: Session, id_proyecto: int, ruta_pdf: str, declaracion: bool) -> Dict[str, Any]:
        memoria = db.scalars(select(MemoriaDescriptiva).where(MemoriaDescriptiva.id_proyecto == id_proyecto)).first()
        if memoria is None:
            memoria = MemoriaDescriptiva(id_proyecto=id_proyecto)
            db.add(memoria)
        memoria.ruta_pdf = ruta_pdf
        memoria.declaracion_decreto_351_79 = declaracion
        commit_or_rollback(db)
        db.refresh(memoria)
        return to_dict(memoria)
