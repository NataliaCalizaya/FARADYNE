from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.repositories.utils import commit_or_rollback, to_dict


class UsuarioRepository:

    @staticmethod
    def get_by_id(db: Session, id_usuario: int) -> Optional[Dict[str, Any]]:
        return to_dict(db.get(Usuario, id_usuario))

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[Dict[str, Any]]:
        stmt = select(Usuario).where(func.lower(Usuario.email) == email.lower())
        return to_dict(db.scalars(stmt).first())

    @staticmethod
    def create_usuario(db: Session, nombre: str, email: str, password_hash: str) -> Dict[str, Any]:
        usuario = Usuario(nombre=nombre, email=email.lower(), password_hash=password_hash)
        db.add(usuario)
        commit_or_rollback(db)
        db.refresh(usuario)
        return to_dict(usuario)