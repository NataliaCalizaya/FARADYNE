from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.modelo2d import Modelo2D
from app.models.plano import Plano
from app.models.proyecto import Proyecto
from app.repositories.utils import commit_or_rollback, execute_returning_one, to_dict


class PlanoRepository:

    @staticmethod
    def get_proyecto_by_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Devuelve el proyecto por id, o None si no existe (ya no se crea uno de relleno)."""
        return to_dict(db.get(Proyecto, id_proyecto))

    @staticmethod
    def create_plano(
        db: Session,
        id_proyecto: int,
        nombre_archivo: str,
        tipo_archivo: str,
        ruta_archivo: str,
        tamano_bytes: int = 0,
        metadatos: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Guarda la metadata del plano.

        La BD tiene un CHECK: tipo_archivo solo acepta 'DXF' o 'PDF' (mayúsculas).
        """
        plano = Plano(
            id_proyecto=id_proyecto,
            nombre_archivo=nombre_archivo,
            tipo_archivo=tipo_archivo,
            ruta_archivo=ruta_archivo,
            tamano_bytes=tamano_bytes,
            metadatos=metadatos or {},
        )
        db.add(plano)
        commit_or_rollback(db)
        db.refresh(plano)
        return to_dict(plano)

    @staticmethod
    def create_modelo2d(
        db: Session,
        id_plano: int,
        id_proyecto: Optional[int] = None,  # Ya no se usa: modelo2d no tiene id_proyecto. Se deja por compatibilidad.
        poligonos: Optional[List[Dict[str, Any]]] = None,
        capas: Optional[List[Dict[str, Any]]] = None,
        cotas_altura: Optional[List[Dict[str, Any]]] = None,
        lineas: Optional[List[Dict[str, Any]]] = None,
        colores: Optional[List[Dict[str, Any]]] = None,
        validado: bool = False,
    ) -> Dict[str, Any]:
        """Guarda el modelo 2D parseado.

        modelo2d.id_plano es UNIQUE (1:1 con plano), por eso es un upsert:
        si ya existe un modelo2d para ese plano, se sobrescribe.
        """
        stmt = pg_insert(Modelo2D).values(
            id_plano=id_plano,
            poligonos=poligonos or [],
            lineas=lineas or [],
            capas=capas or [],
            colores=colores or [],
            cotas_altura=cotas_altura or [],
            validado=validado,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["id_plano"],
            set_={
                col: getattr(stmt.excluded, col)
                for col in ("poligonos", "lineas", "capas", "colores", "cotas_altura", "validado")
            },
        ).returning(Modelo2D.__table__)
        return execute_returning_one(db, stmt)

    @staticmethod
    def update_modelo2d(
        db: Session,
        id_modelo2d: int,
        poligonos: Optional[List[Dict[str, Any]]] = None,
        lineas: Optional[List[Dict[str, Any]]] = None,
        capas: Optional[List[Dict[str, Any]]] = None,
        cotas_altura: Optional[List[Dict[str, Any]]] = None,
        colores: Optional[List[Dict[str, Any]]] = None,
        validado: Optional[bool] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza geometría y estado de validación del modelo 2D. None si no existe."""
        modelo = db.get(Modelo2D, id_modelo2d)
        if modelo is None:
            return None

        if poligonos is not None:
            modelo.poligonos = poligonos
        if lineas is not None:
            modelo.lineas = lineas
        if capas is not None:
            modelo.capas = capas
        if cotas_altura is not None:
            modelo.cotas_altura = cotas_altura
        if colores is not None:
            modelo.colores = colores
        if validado is not None:
            modelo.validado = validado

        commit_or_rollback(db)
        db.refresh(modelo)
        return to_dict(modelo)

    @staticmethod
    def get_plano_by_id(db: Session, id_plano: int) -> Optional[Dict[str, Any]]:
        """Busca un plano por su PK."""
        return to_dict(db.get(Plano, id_plano))

    @staticmethod
    def get_modelo2d_by_plano_id(db: Session, id_plano: int) -> Optional[Dict[str, Any]]:
        """Busca el modelo2d asociado a un plano (1:1, id_plano es UNIQUE)."""
        stmt = select(Modelo2D).where(Modelo2D.id_plano == id_plano)
        return to_dict(db.scalars(stmt).first())

    @staticmethod
    def get_modelo2d_by_id(db: Session, id_modelo2d: int) -> Optional[Dict[str, Any]]:
        """Busca un modelo2d por su PK."""
        return to_dict(db.get(Modelo2D, id_modelo2d))
