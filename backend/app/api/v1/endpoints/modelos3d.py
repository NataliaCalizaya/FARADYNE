from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.common import to_int
from app.core.database import get_db
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.plano_repository import PlanoRepository
from app.schemas.modelo3d_schema import (
    Modelo3DCreateRequest,
    Modelo3DResponse,
    ResetViewRequest,
    ResetViewResponse,
)
from app.services.model3d_generator_service import Model3DGeneratorService

router = APIRouter(prefix="/modelos3d", tags=["HU03 - Modelo 3D"])

VISTA_DEFECTO = {"camera": [50, 50, 50], "target": [0, 0, 0]}


def _id_proyecto_de_modelo2d(db: Session, id_modelo2d: int) -> str:
    """modelo3d -> modelo2d -> plano -> proyecto ('' si la cadena está cortada)."""
    modelo2d = PlanoRepository.get_modelo2d_by_id(db, id_modelo2d)
    if not modelo2d or not modelo2d.get("id_plano"):
        return ""
    plano = PlanoRepository.get_plano_by_id(db, modelo2d["id_plano"])
    return str(plano["id_proyecto"]) if plano else ""


def _respuesta(modelo3d: Dict[str, Any], id_proyecto: str) -> Dict[str, Any]:
    return {
        "id": str(modelo3d["id_modelo3d"]),
        "id_modelo2d": str(modelo3d["id_modelo2d"]),
        "id_proyecto": id_proyecto,
        "geometria_volumetrica": modelo3d.get("geometria_volumetrica") or {},
        "vista_defecto": modelo3d.get("vista_defecto") or dict(VISTA_DEFECTO),
        "creado_en": modelo3d.get("creado_en"),
        "actualizado_en": modelo3d.get("actualizado_en"),
    }


@router.post("", response_model=Modelo3DResponse, status_code=status.HTTP_201_CREATED)
def create_modelo3d(payload: Modelo3DCreateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """HU03: extrusión volumétrica 3D determinista a partir de un Modelo 2D."""
    id_modelo2d = to_int(payload.id_modelo2d, "id_modelo2d")

    modelo2d = PlanoRepository.get_modelo2d_by_id(db, id_modelo2d)
    if not modelo2d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 2D con ID '{id_modelo2d}'.",
        )
    if not modelo2d.get("validado"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La geometría 2D debe estar validada antes de generar el modelo 3D.",
        )

    mesh_data = Model3DGeneratorService.generate_3d_mesh_from_2d(modelo2d)
    vista_defecto = mesh_data.get("vista_defecto") or dict(VISTA_DEFECTO)

    # Upsert (modelo3d.id_modelo2d es UNIQUE): regenera si ya existía.
    modelo3d_db = Modelo3DRepository.create_modelo3d(
        db,
        id_modelo2d=id_modelo2d,
        geometria_volumetrica=mesh_data,
        vista_defecto=vista_defecto,
    )
    return _respuesta(modelo3d_db, _id_proyecto_de_modelo2d(db, id_modelo2d))


@router.get("/by-modelo2d/{id_modelo2d}", response_model=Modelo3DResponse)
def get_modelo3d_by_modelo2d(id_modelo2d: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Modelo 3D asociado a un Modelo 2D (si existe)."""
    modelo3d = Modelo3DRepository.get_modelo3d_by_modelo2d_id(db, id_modelo2d)
    if not modelo3d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró un Modelo 3D para el Modelo 2D '{id_modelo2d}'.",
        )
    return _respuesta(modelo3d, _id_proyecto_de_modelo2d(db, id_modelo2d))


@router.get("/{id}", response_model=Modelo3DResponse)
def get_modelo3d(id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """HU03: geometría 3D generada para el visor."""
    modelo3d = Modelo3DRepository.get_modelo3d_by_id(db, id)
    if not modelo3d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 3D con ID '{id}'.",
        )
    return _respuesta(modelo3d, _id_proyecto_de_modelo2d(db, modelo3d["id_modelo2d"]))


@router.patch("/{id}/reset-view", response_model=ResetViewResponse)
def reset_modelo3d_view(
    id: int,
    payload: ResetViewRequest = ResetViewRequest(),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """HU03: restablece cámara y target por defecto del visor 3D."""
    modelo3d = Modelo3DRepository.get_modelo3d_by_id(db, id)
    if not modelo3d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 3D con ID '{id}'.",
        )

    # dict() copia: si se muta el mismo objeto JSONB que tiene el ORM,
    # SQLAlchemy no detecta el cambio y no emite el UPDATE.
    default_view = dict(modelo3d.get("vista_defecto") or VISTA_DEFECTO)
    if payload.camera:
        default_view["camera"] = payload.camera
    if payload.target:
        default_view["target"] = payload.target

    updated_db = Modelo3DRepository.update_vista_defecto(db, id, default_view)

    return {
        "id": str(id),
        "vista_defecto": (updated_db or {}).get("vista_defecto", default_view),
        "mensaje": "Vista restablecida a su posición por defecto correctamente.",
    }
