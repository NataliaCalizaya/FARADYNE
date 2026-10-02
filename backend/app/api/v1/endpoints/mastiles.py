from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.common import to_int
from app.core.database import get_db
from app.repositories.mastil_repository import MastilRepository
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.plano_repository import PlanoRepository
from app.schemas.mastil_schema import (
    MastilCreateRequest,
    MastilResponse,
    MastilUpdateRequest,
)
from app.services.model3d_generator_service import get_altura_en_punto

router = APIRouter(prefix="/mastiles", tags=["HU05 - Mástiles Captores"])


def _resolve_modelo3d(db: Session, payload: MastilCreateRequest) -> Dict[str, Any]:
    """Resuelve el Modelo 3D a partir de id_modelo3d o id_modelo2d."""
    if payload.id_modelo3d:
        id_modelo3d = to_int(payload.id_modelo3d, "id_modelo3d")
        modelo3d = Modelo3DRepository.get_modelo3d_by_id(db, id_modelo3d)
        if not modelo3d:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el Modelo 3D con ID '{id_modelo3d}'.",
            )
        return modelo3d

    if payload.id_modelo2d:
        id_modelo2d = to_int(payload.id_modelo2d, "id_modelo2d")
        modelo3d = Modelo3DRepository.get_modelo3d_by_modelo2d_id(db, id_modelo2d)
        if not modelo3d:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No se encontró un Modelo 3D asociado al Modelo 2D '{id_modelo2d}'. "
                    "Genere el Modelo 3D primero."
                ),
            )
        return modelo3d

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Debe proveer 'id_modelo3d' o 'id_modelo2d'.",
    )


@router.post("", response_model=MastilResponse, status_code=status.HTTP_201_CREATED)
def create_mastil(payload: MastilCreateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    modelo3d = _resolve_modelo3d(db, payload)

    id_modelo2d = modelo3d.get("id_modelo2d")
    if not id_modelo2d:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El Modelo 3D no tiene un Modelo 2D asociado.",
        )

    # Z automática: el front manda 0 por defecto, así que 0 se trata como
    # "sin especificar" y se resuelve con la altura del polígono bajo el punto.
    posicion_z = payload.posicion_z or 0.0
    if not payload.posicion_z:
        modelo2d = PlanoRepository.get_modelo2d_by_id(db, id_modelo2d)
        if modelo2d:
            posicion_z = get_altura_en_punto(
                modelo2d.get("poligonos") or [],
                payload.posicion_x,
                payload.posicion_y,
                default=0.0,
            )

    return MastilRepository.create_mastil(
        db,
        id_modelo2d=id_modelo2d,
        posicion_x=payload.posicion_x,
        posicion_y=payload.posicion_y,
        posicion_z=posicion_z,
        altura=payload.altura,
        tipo=payload.tipo,
        radio_cobertura=payload.altura * 2.0,
    )


@router.get("/modelo3d/{id_modelo3d}", response_model=List[MastilResponse])
def get_mastiles_by_modelo3d(id_modelo3d: str, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """HU05: mástiles de un Modelo 3D. ID inválido o inexistente -> lista vacía
    (no es error fatal en la página de mástiles)."""
    try:
        id_int = int(id_modelo3d)
    except ValueError:
        return []
    return MastilRepository.get_mastiles_by_modelo3d_id(db, id_int)


@router.get("/modelo2d/{id_modelo2d}", response_model=List[MastilResponse])
def get_mastiles_by_modelo2d(id_modelo2d: int, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """HU05: mástiles asociados a un Modelo 2D."""
    return MastilRepository.get_mastiles_by_modelo2d_id(db, id_modelo2d)


@router.put("/{id}", response_model=MastilResponse)
def update_mastil(id: int, payload: MastilUpdateRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """HU05: mueve o actualiza un mástil (coordenadas, altura o tipo)."""
    existing = MastilRepository.get_mastil_by_id(db, id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el mástil con ID '{id}'.",
        )

    se_movio = payload.posicion_x is not None or payload.posicion_y is not None
    posicion_z = payload.posicion_z

    if se_movio and posicion_z is None:
        posicion_x = payload.posicion_x if payload.posicion_x is not None else existing["posicion_x"]
        posicion_y = payload.posicion_y if payload.posicion_y is not None else existing["posicion_y"]

        id_modelo2d = existing.get("id_modelo2d")
        modelo2d = PlanoRepository.get_modelo2d_by_id(db, int(id_modelo2d)) if id_modelo2d else None
        if modelo2d:
            posicion_z = get_altura_en_punto(
                modelo2d.get("poligonos") or [], posicion_x, posicion_y, default=0.0
            )

    return MastilRepository.update_mastil(
        db,
        id_mastil=id,
        posicion_x=payload.posicion_x,
        posicion_y=payload.posicion_y,
        posicion_z=posicion_z,
        altura=payload.altura,
        tipo=payload.tipo,
    ) or existing


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_mastil(id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """HU05: elimina un mástil por ID."""
    deleted = MastilRepository.delete_mastil(db, id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el mástil con ID '{id}'.",
        )
    return {"id": str(id), "mensaje": "Mástil eliminado exitosamente.", "exito": True}
