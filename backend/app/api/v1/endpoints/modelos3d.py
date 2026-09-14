from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
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


@router.post("", response_model=Modelo3DResponse, status_code=status.HTTP_201_CREATED)
def create_modelo3d(payload: Modelo3DCreateRequest) -> Dict[str, Any]:
    """HU03: Trigger deterministic programmatic 3D volumetric extrusion from 2D model ID."""
    modelo2d = PlanoRepository.get_modelo2d_by_id(payload.id_modelo2d)
    if not modelo2d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 2D con ID '{payload.id_modelo2d}'.",
        )

    if not modelo2d.get("validado"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La geometría 2D debe estar validada antes de generar el modelo 3D.",
        )


    # Deterministic generation
    mesh_data = Model3DGeneratorService.generate_3d_mesh_from_2d(modelo2d)
    id_proyecto = str(modelo2d["id_proyecto"])
    vista_defecto = mesh_data.get("vista_defecto", {"camera": [50, 50, 50], "target": [0, 0, 0]})

    # Save to table 'modelo3d'
    modelo3d_db = Modelo3DRepository.create_modelo3d(
        id_modelo2d=payload.id_modelo2d,
        id_proyecto=id_proyecto,
        geometria_volumetrica=mesh_data,
        vista_defecto=vista_defecto,
    )

    id_3d = str(modelo3d_db.get("id_modelo3d", modelo3d_db.get("id", "")))
    id_2d = str(modelo3d_db.get("id_modelo2d", payload.id_modelo2d))

    return {
        "id": id_3d,
        "id_modelo2d": id_2d,
        "id_proyecto": id_proyecto,
        "geometria_volumetrica": modelo3d_db.get("geometria_volumetrica", {}),
        "vista_defecto": vista_defecto,
        "fecha_creacion": modelo3d_db.get("fecha_generacion") or modelo3d_db.get("fecha_creacion"),
    }


@router.get("/{id}", response_model=Modelo3DResponse)
def get_modelo3d(id: str) -> Dict[str, Any]:
    """HU03: Retrieve generated 3D geometry for model viewer."""
    modelo3d = Modelo3DRepository.get_modelo3d_by_id(id)
    if not modelo3d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 3D con ID '{id}'.",
        )

    id_3d = str(modelo3d.get("id_modelo3d", modelo3d.get("id", id)))
    id_2d = str(modelo3d.get("id_modelo2d", ""))

    return {
        "id": id_3d,
        "id_modelo2d": id_2d,
        "id_proyecto": str(modelo3d.get("id_proyecto", "")),
        "geometria_volumetrica": modelo3d.get("geometria_volumetrica", {}),
        "vista_defecto": modelo3d.get("vista_defecto", {"camera": [50, 50, 50], "target": [0, 0, 0]}),
        "fecha_creacion": modelo3d.get("fecha_generacion") or modelo3d.get("fecha_creacion"),
    }



@router.patch("/{id}/reset-view", response_model=ResetViewResponse)
def reset_modelo3d_view(id: str, payload: ResetViewRequest = ResetViewRequest()) -> Dict[str, Any]:
    """HU03: Reset 3D viewer default camera position and focus target."""
    modelo3d = Modelo3DRepository.get_modelo3d_by_id(id)
    if not modelo3d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 3D con ID '{id}'.",
        )

    default_view = modelo3d.get("vista_defecto", {"camera": [50, 50, 50], "target": [0, 0, 0]})
    if payload.camera:
        default_view["camera"] = payload.camera
    if payload.target:
        default_view["target"] = payload.target

    updated_db = Modelo3DRepository.update_vista_defecto(id, default_view)

    return {
        "id": id,
        "vista_defecto": updated_db.get("vista_defecto", default_view) if updated_db else default_view,
        "mensaje": "Vista restablecida a su posición por defecto correctamente.",
    }
