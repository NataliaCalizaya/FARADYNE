from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.mastil import Mastil
from app.models.modelo2d import Modelo2D
from app.models.modelo3d import Modelo3D
from app.models.plano import Plano
from app.repositories.utils import commit_or_rollback


def _to_float(value: Any, default: float = 0.0) -> float:
    """float() que tolera NULL (posicion_z es nullable en la BD)."""
    return float(value) if value is not None else default


def _map_mastil(m: Mastil) -> Dict[str, Any]:
    """Normaliza un Mastil al contrato del schema MastilResponse."""
    return {
        "id": str(m.id_mastil),
        "id_modelo2d": str(m.id_modelo2d),
        "posicion_x": _to_float(m.posicion_x),
        "posicion_y": _to_float(m.posicion_y),
        "posicion_z": _to_float(m.posicion_z),
        "altura": _to_float(m.altura),
        "tipo": str(m.tipo or "Franklin"),
        "radio_cobertura": m.radio_cobertura,
    }


class MastilRepository:

    @staticmethod
    def create_mastil(
        db: Session,
        id_modelo2d: int,
        posicion_x: float = 0.0,
        posicion_y: float = 0.0,
        posicion_z: float = 0.0,
        altura: float = 0.0,
        tipo: str = "Franklin",
        radio_cobertura: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Persiste un nuevo mástil captor (tipo: máx. 50 caracteres)."""
        mastil = Mastil(
            id_modelo2d=id_modelo2d,
            posicion_x=posicion_x,
            posicion_y=posicion_y,
            posicion_z=posicion_z,
            altura=altura,
            tipo=tipo,
            radio_cobertura=radio_cobertura,
        )
        db.add(mastil)
        commit_or_rollback(db)
        db.refresh(mastil)
        return _map_mastil(mastil)

    @staticmethod
    def update_mastil(
        db: Session,
        id_mastil: int,
        posicion_x: Optional[float] = None,
        posicion_y: Optional[float] = None,
        posicion_z: Optional[float] = None,
        altura: Optional[float] = None,
        tipo: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza coordenadas, altura o tipo del mástil. None si no existe."""
        mastil = db.get(Mastil, id_mastil)
        if mastil is None:
            return None

        if posicion_x is not None:
            mastil.posicion_x = posicion_x
        if posicion_y is not None:
            mastil.posicion_y = posicion_y
        if posicion_z is not None:
            mastil.posicion_z = posicion_z
        if altura is not None:
            mastil.altura = altura
        if tipo is not None:
            mastil.tipo = tipo

        commit_or_rollback(db)
        db.refresh(mastil)
        return _map_mastil(mastil)

    @staticmethod
    def delete_mastil(db: Session, id_mastil: int) -> bool:
        """Elimina un mástil por clave primaria. Devuelve False si no existía."""
        mastil = db.get(Mastil, id_mastil)
        if mastil is None:
            return False
        db.delete(mastil)
        commit_or_rollback(db)
        return True

    @staticmethod
    def get_mastil_by_id(db: Session, id_mastil: int) -> Optional[Dict[str, Any]]:
        """Obtiene un mástil por clave primaria."""
        mastil = db.get(Mastil, id_mastil)
        return _map_mastil(mastil) if mastil else None

    @staticmethod
    def get_mastiles_by_proyecto_id(db: Session, id_proyecto: int) -> List[Dict[str, Any]]:
        """Todos los mástiles de un proyecto, vía modelo2d → plano → proyecto
        (la tabla 'mastil' no tiene id_proyecto directo, solo id_modelo2d)."""
        stmt = (
            select(Mastil)
            .join(Modelo2D, Mastil.id_modelo2d == Modelo2D.id_modelo2d)
            .join(Plano, Modelo2D.id_plano == Plano.id_plano)
            .where(Plano.id_proyecto == id_proyecto)
            .order_by(Mastil.id_mastil.asc())
        )
        return [_map_mastil(m) for m in db.scalars(stmt).all()]

    @staticmethod
    def get_mastiles_by_modelo3d_id(db: Session, id_modelo3d: int) -> List[Dict[str, Any]]:
        """Todos los mástiles asociados a un modelo 3D mediante modelo2d."""
        stmt = (
            select(Mastil)
            .join(Modelo3D, Mastil.id_modelo2d == Modelo3D.id_modelo2d)
            .where(Modelo3D.id_modelo3d == id_modelo3d)
            .order_by(Mastil.id_mastil.asc())
        )
        return [_map_mastil(m) for m in db.scalars(stmt).all()]

    @staticmethod
    def get_mastiles_by_modelo2d_id(db: Session, id_modelo2d: int) -> List[Dict[str, Any]]:
        """Mástiles asociados directamente a un modelo 2D mediante la FK id_modelo2d."""
        stmt = (
            select(Mastil)
            .where(Mastil.id_modelo2d == id_modelo2d)
            .order_by(Mastil.id_mastil.asc())
        )
        return [_map_mastil(m) for m in db.scalars(stmt).all()]
