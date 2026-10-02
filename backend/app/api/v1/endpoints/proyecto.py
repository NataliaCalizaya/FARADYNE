from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.proyecto_repository import ProyectoRepository
from app.schemas.proyecto_schema import ProyectoCompletoResponse, ProyectoUbicacionResponse

router = APIRouter(prefix="/proyectos", tags=["Proyectos"])


# ------------------------------------------------------------------ #
# SCHEMAS INTERNOS
# ------------------------------------------------------------------ #
class ProyectoCreateRequest(BaseModel):
    nombre: str
    cliente: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    fecha_del_proyecto: Optional[date] = None
    estado: str = "borrador"


class ProyectoUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    cliente: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    fecha_del_proyecto: Optional[date] = None
    estado: Optional[str] = None


# ------------------------------------------------------------------ #
# ENDPOINTS
# ------------------------------------------------------------------ #
@router.get("", response_model=List[Dict[str, Any]])
def listar_proyectos(db: Session = Depends(get_db)):
    return [_format_proyecto(p) for p in ProyectoRepository.list_proyectos(db)]


@router.post("", status_code=201)
def crear_proyecto(payload: ProyectoCreateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        proyecto = ProyectoRepository.create_proyecto(
            db,
            nombre=payload.nombre,
            cliente=payload.cliente,
            descripcion=payload.descripcion,
            ubicacion=payload.ubicacion,
            departamento=payload.departamento,
            provincia=payload.provincia,
            localidad=payload.localidad,
            fecha_del_proyecto=payload.fecha_del_proyecto,
            estado=payload.estado,
        )
    except ValueError as err:  # cliente / ubicacion obligatorios
        raise HTTPException(status_code=422, detail=str(err))
    if not proyecto:
        raise HTTPException(status_code=500, detail="Error al crear el proyecto.")
    return _format_proyecto(proyecto)


@router.get("/{id_proyecto}", response_model=Dict[str, Any])
def obtener_proyecto(id_proyecto: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    proyecto = ProyectoRepository.get_proyecto_by_id(db, id_proyecto)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return _format_proyecto(proyecto)


@router.patch("/{id_proyecto}", response_model=Dict[str, Any])
def actualizar_proyecto(
    id_proyecto: int, payload: ProyectoUpdateRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    # update_proyecto ya devuelve None si no existe.
    updated = ProyectoRepository.update_proyecto(
        db,
        id_proyecto=id_proyecto,
        nombre=payload.nombre,
        cliente=payload.cliente,
        descripcion=payload.descripcion,
        ubicacion=payload.ubicacion,
        departamento=payload.departamento,
        provincia=payload.provincia,
        localidad=payload.localidad,
        fecha_del_proyecto=payload.fecha_del_proyecto,
        estado=payload.estado,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return _format_proyecto(updated)


@router.get("/{id_proyecto}/ubicacion", response_model=ProyectoUbicacionResponse)
def obtener_ubicacion_proyecto(id_proyecto: int, db: Session = Depends(get_db)):
    proyecto = ProyectoRepository.get_ubicacion_by_proyecto_id(db, id_proyecto)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return {
        "id_proyecto": str(proyecto.get("id_proyecto", id_proyecto)),
        "nombre": proyecto.get("nombre", ""),
        "localidad": proyecto.get("localidad"),
    }


@router.get("/{id_proyecto}/completo", response_model=ProyectoCompletoResponse)
def obtener_proyecto_completo(id_proyecto: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Proyecto con IDs derivados (id_plano, id_modelo2d, id_modelo3d,
    geometria_validada) para reconstruir el estado del frontend al abrir una
    URL directa. 404 si el proyecto no existe."""
    row = ProyectoRepository.get_proyecto_completo_by_id(db, id_proyecto)
    if not row:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return {
        "id_proyecto": str(row["id_proyecto"]),
        "nombre": row.get("nombre", ""),
        "cliente": row.get("cliente"),
        "descripcion": row.get("descripcion"),
        "ubicacion": row.get("ubicacion"),
        "departamento": row.get("departamento"),
        "provincia": row.get("provincia"),
        "localidad": row.get("localidad"),
        "estado": row.get("estado", "borrador"),
        "fecha_creacion": row.get("fecha_creacion"),
        "fecha_del_proyecto": row.get("fecha_del_proyecto"),
        "id_plano": str(row["id_plano"]) if row.get("id_plano") else None,
        "id_modelo2d": str(row["id_modelo2d"]) if row.get("id_modelo2d") else None,
        "id_modelo3d": str(row["id_modelo3d"]) if row.get("id_modelo3d") else None,
        "geometria_validada": bool(row.get("geometria_validada", False)),
    }


# ------------------------------------------------------------------ #
# UTILIDAD
# ------------------------------------------------------------------ #
def _format_proyecto(row: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza la fila de BD al contrato de respuesta del endpoint."""
    return {
        "id_proyecto": str(row.get("id_proyecto", "")),
        "nombre": row.get("nombre", ""),
        "cliente": row.get("cliente"),
        "descripcion": row.get("descripcion"),
        "ubicacion": row.get("ubicacion"),
        "departamento": row.get("departamento"),
        "provincia": row.get("provincia"),
        "localidad": row.get("localidad"),
        "estado": row.get("estado", "borrador"),
        "fecha_creacion": row.get("fecha_creacion"),
        "fecha_del_proyecto": row.get("fecha_del_proyecto"),
    }
