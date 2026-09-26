from datetime import date
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.repositories.proyecto_repository import ProyectoRepository
from app.schemas.proyecto_schema import ProyectoUbicacionResponse

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
def listar_proyectos():
    proyectos = ProyectoRepository.list_proyectos()
    return [_format_proyecto(p) for p in proyectos]

@router.post("", status_code=201)
def crear_proyecto(payload: ProyectoCreateRequest) -> Dict[str, Any]:
    proyecto = ProyectoRepository.create_proyecto(
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
    if not proyecto:
        raise HTTPException(status_code=500, detail="Error al crear el proyecto.")
    return _format_proyecto(proyecto)

@router.get("/{id_proyecto}", response_model=Dict[str, Any])
def obtener_proyecto(id_proyecto: str) -> Dict[str, Any]:
    proyecto = ProyectoRepository.get_proyecto_by_id(id_proyecto)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return _format_proyecto(proyecto)

@router.patch("/{id_proyecto}", response_model=Dict[str, Any])
def actualizar_proyecto(id_proyecto: str, payload: ProyectoUpdateRequest) -> Dict[str, Any]:
    proyecto = ProyectoRepository.get_proyecto_by_id(id_proyecto)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    updated = ProyectoRepository.update_proyecto(
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
    return _format_proyecto(updated or proyecto)

@router.get("/{id_proyecto}/ubicacion", response_model=ProyectoUbicacionResponse)
def obtener_ubicacion_proyecto(id_proyecto: str):
    proyecto = ProyectoRepository.get_ubicacion_by_proyecto_id(id_proyecto)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return {
        "id_proyecto": str(proyecto.get("id_proyecto", id_proyecto)),
        "nombre": proyecto.get("nombre", ""),
        "localidad": proyecto.get("localidad"),
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