from typing import Any, Dict, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session


def to_dict(obj: Any) -> Optional[Dict[str, Any]]:
    """Convierte una instancia ORM en un dict {columna: valor}. None -> None.

    Los repositories devuelven dicts (igual que antes con el SQL puro) para
    no romper a los services/routers que ya consumen row["campo"].
    """
    if obj is None:
        return None
    mapper = inspect(obj).mapper
    return {attr.key: getattr(obj, attr.key) for attr in mapper.column_attrs}


def commit_or_rollback(db: Session) -> None:
    """Commit; si falla, hace rollback para dejar la sesión usable y re-lanza el error."""
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def execute_returning_one(db: Session, stmt: Any) -> Dict[str, Any]:
    """Ejecuta un INSERT/UPSERT con RETURNING, hace commit y devuelve la fila como dict."""
    try:
        row = db.execute(stmt).mappings().one()
        db.commit()
    except Exception:
        db.rollback()
        raise
    return dict(row)
