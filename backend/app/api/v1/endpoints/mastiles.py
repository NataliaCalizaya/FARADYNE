from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status
from app.repositories.mastil_repository import MastilRepository
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.schemas.mastil_schema import (
    CoberturaResponse,
    MastilCreateRequest,
    MastilResponse,
    MastilUpdateRequest,
)
from app.services.spda_service import SPDAService

router = APIRouter(prefix="/mastiles", tags=["HU05 - Mástiles Captores"])


@router.post("", response_model=MastilResponse, status_code=status.HTTP_201_CREATED)
def create_mastil(payload: MastilCreateRequest) -> Dict[str, Any]:
    """HU05: Add an air terminal mast (captor) to a 3D model."""
    modelo3d = Modelo3DRepository.get_modelo3d_by_id(payload.id_modelo3d)
    if not modelo3d:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el Modelo 3D con ID '{payload.id_modelo3d}'.",
        )

    id_proyecto = payload.id_proyecto or str(modelo3d["id_proyecto"])

    # Basic protection radius calculation (default 30m)
    radio_cobertura = payload.altura * 2.0

    mastil_db = MastilRepository.create_mastil(
        id_modelo3d=payload.id_modelo3d,
        id_proyecto=id_proyecto,
        posicion_x=payload.posicion_x,
        posicion_y=payload.posicion_y,
        posicion_z=payload.posicion_z,
        altura=payload.altura,
        tipo=payload.tipo,
        radio_cobertura=radio_cobertura,
        angulo_proteccion=45.0,
    )

    id_mast = str(mastil_db.get("id_mastil", mastil_db.get("id", "")))
    x_val = float(mastil_db.get("coordenada_x", payload.posicion_x))
    y_val = float(mastil_db.get("coordenada_y", payload.posicion_y))

    return {
        "id": id_mast,
        "id_modelo3d": str(mastil_db.get("id_modelo3d", payload.id_modelo3d)),
        "id_proyecto": str(id_proyecto),
        "posicion_x": x_val,
        "posicion_y": y_val,
        "posicion_z": payload.posicion_z,
        "altura": float(mastil_db.get("altura", payload.altura)),
        "tipo": str(mastil_db.get("tipo", payload.tipo)),
        "radio_cobertura": radio_cobertura,
        "angulo_proteccion": 45.0,
        "fecha_creacion": mastil_db.get("fecha_creacion"),
    }


@router.put("/{id}", response_model=MastilResponse)
def update_mastil(id: str, payload: MastilUpdateRequest) -> Dict[str, Any]:
    """HU05: Move air terminal mast (update x, y, z coordinates, height or type)."""
    existing = MastilRepository.get_mastil_by_id(id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el mástil con ID '{id}'.",
        )

    updated_db = MastilRepository.update_mastil(
        id_mastil=id,
        posicion_x=payload.posicion_x,
        posicion_y=payload.posicion_y,
        posicion_z=payload.posicion_z,
        altura=payload.altura,
        tipo=payload.tipo,
    ) or existing

    id_mast = str(updated_db.get("id_mastil", updated_db.get("id", id)))
    x_val = float(updated_db.get("coordenada_x", payload.posicion_x if payload.posicion_x is not None else 0.0))
    y_val = float(updated_db.get("coordenada_y", payload.posicion_y if payload.posicion_y is not None else 0.0))

    return {
        "id": id_mast,
        "id_modelo3d": str(updated_db.get("id_modelo3d", "")),
        "id_proyecto": str(updated_db.get("id_proyecto", "")),
        "posicion_x": x_val,
        "posicion_y": y_val,
        "posicion_z": payload.posicion_z if payload.posicion_z is not None else 0.0,
        "altura": float(updated_db.get("altura", payload.altura if payload.altura is not None else 0.0)),
        "tipo": str(updated_db.get("tipo", payload.tipo if payload.tipo is not None else "Franklin")),
        "radio_cobertura": updated_db.get("radio_cobertura"),
        "angulo_proteccion": updated_db.get("angulo_proteccion", 45.0),
        "fecha_creacion": updated_db.get("fecha_creacion"),
    }


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_mastil(id: str) -> Dict[str, Any]:
    """HU05: Delete an air terminal mast by ID."""
    existing = MastilRepository.get_mastil_by_id(id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el mástil con ID '{id}'.",
        )

    deleted = MastilRepository.delete_mastil(id)
    return {"id": id, "mensaje": "Mástil eliminado exitosamente.", "exito": deleted}


@router.get("/proyecto/{idProyecto}/cobertura", response_model=CoberturaResponse)
def get_cobertura_mastiIes(idProyecto: str) -> Dict[str, Any]:
    """HU05: Evaluate SPDA protection coverage for all placed masts in a project using Rolling Sphere Method."""
    # 1. Fetch protection level calculated in HU04
    nivel_db = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(idProyecto)
    nivel_str = "Nivel II"
    rolling_radius = 30.0

    if nivel_db:
        nivel_str = nivel_db.get("nivel") or nivel_db.get("nivel_proteccion_calculado") or "Nivel II"
        if "Nivel I" in nivel_str:
            rolling_radius = 20.0
        elif "Nivel II" in nivel_str:
            rolling_radius = 30.0
        elif "Nivel III" in nivel_str:
            rolling_radius = 45.0
        elif "Nivel IV" in nivel_str:
            rolling_radius = 60.0

    # 2. Fetch building 3D model dimensions
    modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(idProyecto)
    dims = {"longitud": 20.0, "anchura": 15.0, "altura": 7.5}
    if modelo3d:
        dims = modelo3d.get("geometria_volumetrica", {}).get("dimensiones", dims)

    # 3. Fetch all masts for project
    masts = MastilRepository.get_mastiles_by_proyecto_id(idProyecto)

    # Convert mast DB dict keys for SPDA evaluation service
    masts_for_eval = [
        {
            "id": m.get("id_mastil", m.get("id")),
            "posicion_x": m.get("coordenada_x", m.get("posicion_x", 0.0)),
            "posicion_y": m.get("coordenada_y", m.get("posicion_y", 0.0)),
            "posicion_z": m.get("posicion_z", 0.0),
            "altura": m.get("altura", 0.0),
            "tipo": m.get("tipo", "Franklin"),
        }
        for m in masts
    ]

    # 4. Run SPDA rolling sphere evaluation
    evaluation = SPDAService.evaluate_masts_coverage(
        masts=masts_for_eval,
        building_dim=dims,
        rolling_sphere_radius=rolling_radius,
    )

    formatted_masts = [
        {
            "id": str(m.get("id_mastil", m.get("id", ""))),
            "id_modelo3d": str(m.get("id_modelo3d", "")),
            "id_proyecto": idProyecto,
            "posicion_x": float(m.get("coordenada_x", m.get("posicion_x", 0.0))),
            "posicion_y": float(m.get("coordenada_y", m.get("posicion_y", 0.0))),
            "posicion_z": float(m.get("posicion_z", 0.0)),
            "altura": float(m.get("altura", 0.0)),
            "tipo": str(m.get("tipo", "Franklin")),
            "radio_cobertura": m.get("radio_cobertura", float(m.get("altura", 0.0)) * 2.0),
            "angulo_proteccion": m.get("angulo_proteccion", 45.0),
            "fecha_creacion": m.get("fecha_creacion"),
        }
        for m in masts
    ]


    return {
        "id_proyecto": idProyecto,
        "nivel_proteccion": nivel_str,
        "radio_esfera_rodante_r": rolling_radius,
        "total_mastiIes": len(masts),
        "mastiIes": formatted_masts,
        "puntos_cobertura": evaluation["puntos_cobertura"],
        "puntos_desprotegidos": evaluation["puntos_desprotegidos"],
        "porcentaje_cobertura": evaluation["porcentaje_cobertura"],
        "advertencias": evaluation["advertencias"],
    }
