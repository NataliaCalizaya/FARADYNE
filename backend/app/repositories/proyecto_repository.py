from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from app.models.modelo2d import Modelo2D
from app.models.modelo3d import Modelo3D
from app.models.plano import Plano
from app.models.proyecto import Proyecto
from app.repositories.utils import commit_or_rollback, to_dict


def _parse_fecha(valor: Any) -> Optional[date]:
    """Acepta None / '' / 'YYYY-MM-DD' / date / datetime y devuelve date o None."""
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


class ProyectoRepository:

    @staticmethod
    def get_proyecto_by_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Fila completa de 'proyecto' por su PK (id_proyecto)."""
        return to_dict(db.get(Proyecto, id_proyecto))

    @staticmethod
    def get_proyecto_completo_by_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Proyecto con IDs derivados (id_plano, id_modelo2d, id_modelo3d,
        geometria_validada) resueltos mediante LEFT JOINs.

        Usado por el frontend para reconstruir el estado completo al abrir una
        URL directa (ej. /proyecto/<id>/mastiles tras F5 o link compartido).
        Usa LEFT JOIN para que funcione con proyectos parciales (sin plano, etc.).
        """
        stmt = (
            select(
                Proyecto.id_proyecto,
                Proyecto.nombre,
                Proyecto.cliente,
                Proyecto.descripcion,
                Proyecto.ubicacion,
                Proyecto.departamento,
                Proyecto.provincia,
                Proyecto.localidad,
                Proyecto.estado,
                Proyecto.fecha_creacion,
                Proyecto.fecha_del_proyecto,
                Plano.id_plano,
                Modelo2D.id_modelo2d,
                func.coalesce(Modelo2D.validado, false()).label("geometria_validada"),
                Modelo3D.id_modelo3d,
            )
            .select_from(Proyecto)
            .outerjoin(Plano, Plano.id_proyecto == Proyecto.id_proyecto)
            .outerjoin(Modelo2D, Modelo2D.id_plano == Plano.id_plano)
            .outerjoin(Modelo3D, Modelo3D.id_modelo2d == Modelo2D.id_modelo2d)
            .where(Proyecto.id_proyecto == id_proyecto)
            .order_by(
                Plano.id_plano.desc().nulls_last(),
                Modelo2D.id_modelo2d.desc().nulls_last(),
                Modelo3D.id_modelo3d.desc().nulls_last(),
            )
            .limit(1)
        )
        row = db.execute(stmt).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def get_ubicacion_by_proyecto_id(db: Session, id_proyecto: int) -> Optional[Dict[str, Any]]:
        """Trae solo id_proyecto/nombre/localidad del proyecto.

        Se usa para mostrar la localidad junto al Ng adoptado en el Paso 1
        del cálculo de Nivel de Protección (HU04), sin traer la fila entera.
        Es la misma columna ('localidad') que se matchea contra
        zona_ceraunica.ciudad para resolver el Ng (ver
        NivelProteccionRepository.get_zona_ceraunica_by_departamento).
        """
        stmt = select(Proyecto.id_proyecto, Proyecto.nombre, Proyecto.localidad).where(
            Proyecto.id_proyecto == id_proyecto
        )
        row = db.execute(stmt).mappings().first()
        return dict(row) if row else None

    @staticmethod
    def list_proyectos(db: Session, id_usuario: int) -> List[Dict[str, Any]]:
        """Devuelve los proyectos del usuario, ordenados por fecha de creación desc."""
        stmt = (
            select(Proyecto)
            .where(Proyecto.id_usuario == id_usuario)   
            .order_by(Proyecto.fecha_creacion.desc())
        )
        return [to_dict(p) for p in db.scalars(stmt).all()]

    @staticmethod
    def create_proyecto(
        db: Session,
        nombre: str,
        fecha_del_proyecto: Optional[str],  # 'YYYY-MM-DD'. Viene del formulario JSX
        cliente: Optional[str] = None,
        ubicacion: Optional[str] = None,
        descripcion: Optional[str] = None,
        departamento: Optional[str] = None,
        provincia: Optional[str] = None,
        localidad: Optional[str] = None,
        estado: str = "borrador",
        id_usuario: Optional[int] = None,

    ) -> Dict[str, Any]:
        """Crea un nuevo proyecto.

        En la BD 'cliente' y 'ubicacion' son NOT NULL, por eso se validan acá
        para devolver un error claro en vez de una violación de constraint.
        """
        if not cliente:
            raise ValueError("'cliente' es obligatorio (columna NOT NULL en proyecto).")
        if not ubicacion:
            raise ValueError("'ubicacion' es obligatoria (columna NOT NULL en proyecto).")

        proyecto = Proyecto(
            nombre=nombre,
            cliente=cliente,
            ubicacion=ubicacion,
            descripcion=descripcion,
            departamento=departamento,
            provincia=provincia,
            localidad=localidad,
            estado=estado,
            fecha_del_proyecto=_parse_fecha(fecha_del_proyecto),
            id_usuario=id_usuario,

        )
        try:
            db.add(proyecto)
            commit_or_rollback(db)
            db.refresh(proyecto)
        except Exception as e:
            print(" ERROR EN BASE DE DATOS AL CREAR PROYECTO:")
            print(e)
            raise
        return to_dict(proyecto)

    @staticmethod
    def update_proyecto(
        db: Session,
        id_proyecto: int,
        nombre: Optional[str] = None,
        cliente: Optional[str] = None,
        descripcion: Optional[str] = None,
        ubicacion: Optional[str] = None,
        departamento: Optional[str] = None,
        provincia: Optional[str] = None,
        localidad: Optional[str] = None,
        estado: Optional[str] = None,
        fecha_del_proyecto: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Actualiza los campos informados de un proyecto. None si no existe."""
        proyecto = db.get(Proyecto, id_proyecto)
        if proyecto is None:
            return None

        if nombre is not None:
            proyecto.nombre = nombre
        if cliente is not None:
            proyecto.cliente = cliente
        if descripcion is not None:
            proyecto.descripcion = descripcion
        if ubicacion is not None:
            proyecto.ubicacion = ubicacion
        if departamento is not None:
            proyecto.departamento = departamento
        if provincia is not None:
            proyecto.provincia = provincia
        if localidad is not None:
            proyecto.localidad = localidad
        if estado is not None:
            proyecto.estado = estado
        if fecha_del_proyecto is not None:
            proyecto.fecha_del_proyecto = _parse_fecha(fecha_del_proyecto)

        commit_or_rollback(db)
        db.refresh(proyecto)
        return to_dict(proyecto)
