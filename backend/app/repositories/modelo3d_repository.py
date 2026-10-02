from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.modelo2d import Modelo2D
from app.models.modelo3d import Modelo3D
from app.models.plano import Plano
from app.repositories.utils import commit_or_rollback, execute_returning_one, to_dict


class Modelo3DRepository:

    @staticmethod
    def create_modelo3d(
        db: Session,
        id_modelo2d: int,
        geometria_volumetrica: Optional[Dict[str, Any]] = None,
        vista_defecto: Optional[Dict[str, Any]] = None,
        escala: Optional[float] = None,
        altura_h: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Guarda la malla volumétrica 3D generada.

        modelo3d.id_modelo2d es UNIQUE (1:1 con modelo2d), por eso es un upsert.
        Si 'escala' o 'altura_h' vienen en None en un upsert, se conserva el
        valor que ya tenía la fila.
        """
        if geometria_volumetrica is None:
            geometria_volumetrica = {}
        if vista_defecto is None:
            vista_defecto = {"camera": [50, 50, 50], "target": [0, 0, 0]}

        stmt = pg_insert(Modelo3D).values(
            id_modelo2d=id_modelo2d,
            geometria_volumetrica=geometria_volumetrica,
            vista_defecto=vista_defecto,
            escala=escala,
            altura_h=altura_h,
            actualizado_en=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id_modelo2d"],
            set_={
                "geometria_volumetrica": stmt.excluded.geometria_volumetrica,
                "vista_defecto": stmt.excluded.vista_defecto,
                "escala": func.coalesce(stmt.excluded.escala, Modelo3D.escala),
                "altura_h": func.coalesce(stmt.excluded.altura_h, Modelo3D.altura_h),
                "actualizado_en": func.now(),
            },
        ).returning(Modelo3D.__table__)
        return execute_returning_one(db, stmt)

    @staticmethod
    def update_modelo3d(
        db: Session,
        id_modelo3d: int,
        geometria_volumetrica: Dict[str, Any],
        vista_defecto: Dict[str, Any],
    ) -> dict:
        """Actualiza geometría y vista por defecto de un modelo 3D existente.

        Actualiza 'actualizado_en' y deja 'creado_en' intacto. {} si no existe.
        """
        modelo = db.get(Modelo3D, id_modelo3d)
        if modelo is None:
            return {}

        modelo.geometria_volumetrica = geometria_volumetrica
        modelo.vista_defecto = vista_defecto
        modelo.actualizado_en = func.now()

        commit_or_rollback(db)
        db.refresh(modelo)
        return to_dict(modelo)

    @staticmethod
    def get_modelo3d_by_id(db: Session, id_modelo3d: int) -> Optional[Dict[str, Any]]:
        """Modelo 3D por su PK."""
        return to_dict(db.get(Modelo3D, id_modelo3d))

    @staticmethod
    def get_modelo3d_by_proyecto_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Modelo 3D más reciente del proyecto, vía modelo2d y plano."""
        stmt = (
            select(Modelo3D)
            .join(Modelo2D, Modelo3D.id_modelo2d == Modelo2D.id_modelo2d)
            .join(Plano, Modelo2D.id_plano == Plano.id_plano)
            .where(Plano.id_proyecto == id_proyecto)
            .order_by(Modelo3D.id_modelo3d.desc())
            .limit(1)
        )
        return to_dict(db.scalars(stmt).first())

    @staticmethod
    def get_modelo3d_by_modelo2d_id(db: Session, id_modelo2d: int) -> dict:
        """Modelo 3D asociado a un modelo 2D (1:1). {} si todavía no existe."""
        stmt = select(Modelo3D).where(Modelo3D.id_modelo2d == id_modelo2d)
        return to_dict(db.scalars(stmt).first()) or {}

    @staticmethod
    def update_vista_defecto(db: Session, id_modelo3d: int, vista_defecto: dict) -> dict:
        """Actualiza la columna jsonb 'vista_defecto'. {} si el modelo no existe."""
        modelo = db.get(Modelo3D, id_modelo3d)
        if modelo is None:
            return {}

        modelo.vista_defecto = vista_defecto
        commit_or_rollback(db)
        db.refresh(modelo)
        return to_dict(modelo)
