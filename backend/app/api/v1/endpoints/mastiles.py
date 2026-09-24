from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, status
from app.repositories.mastil_repository import MastilRepository
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.services.model3d_generator_service import get_altura_en_punto
from app.repositories.plano_repository import PlanoRepository

from app.schemas.mastil_schema import (
    CoberturaResponse,
    MastilCreateRequest,
    MastilResponse,
    MastilUpdateRequest,
)
from app.services.spda_service import SPDAService

router = APIRouter(prefix="/mastiles", tags=["HU05 - Mástiles Captores"])


def _resolve_modelo3d(payload: MastilCreateRequest) -> tuple[Dict[str, Any], str, str]:
    """Resuelve el modelo 3D a partir de id_modelo3d o id_modelo2d.
    
    Devuelve (modelo3d_row, id_modelo3d, id_proyecto).
    """
    # Caso 1: viene id_modelo3d directamente
    if payload.id_modelo3d:
        modelo3d = Modelo3DRepository.get_modelo3d_by_id(payload.id_modelo3d)
        if not modelo3d:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró el Modelo 3D con ID '{payload.id_modelo3d}'.",
            )
        id_modelo3d = payload.id_modelo3d
        id_proyecto = payload.id_proyecto or str(modelo3d.get("id_proyecto", ""))
        return modelo3d, id_modelo3d, id_proyecto

    # Caso 2: viene id_modelo2d → buscar el modelo 3D asociado
    if payload.id_modelo2d:
        modelo3d = Modelo3DRepository.get_modelo3d_by_modelo2d_id(payload.id_modelo2d)
        if not modelo3d:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No se encontró un Modelo 3D asociado al Modelo 2D '{payload.id_modelo2d}'. "
                    "Genere el Modelo 3D primero."
                ),
            )
        id_modelo3d = str(modelo3d.get("id_modelo3d", ""))
        id_proyecto = payload.id_proyecto or str(modelo3d.get("id_proyecto", ""))
        return modelo3d, id_modelo3d, id_proyecto

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Debe proveer 'id_modelo3d' o 'id_modelo2d'.",
    )


# @router.post("", response_model=MastilResponse, status_code=status.HTTP_201_CREATED)
# def create_mastil(payload: MastilCreateRequest) -> Dict[str, Any]:
#     """HU05: Añade un mástil captor a un Modelo 3D.
    
#     Acepta `id_modelo3d` directo o `id_modelo2d` (el endpoint resuelve el modelo 3D).
#     """
#     _modelo3d, id_modelo2d, id_proyecto = _resolve_modelo3d(payload)

#     radio_cobertura = payload.altura * 2.0

#     mastil = MastilRepository.create_mastil(
#         id_modelo2d=id_modelo2d,
#         id_proyecto=id_proyecto or None,
#         posicion_x=payload.posicion_x,
#         posicion_y=payload.posicion_y,
#         posicion_z=payload.posicion_z,
#         altura=payload.altura,
#         tipo=payload.tipo,
#         radio_cobertura=radio_cobertura,
#     )

#     return mastil


@router.post("", response_model=MastilResponse, status_code=status.HTTP_201_CREATED)
def create_mastil(payload: MastilCreateRequest) -> Dict[str, Any]:
    modelo3d, id_modelo3d, id_proyecto = _resolve_modelo3d(payload)

    # Resolver Z automáticamente según el polígono bajo el punto de click.
    id_modelo2d = modelo3d.get("id_modelo2d")
    if not id_modelo2d:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El Modelo 3D no tiene un Modelo 2D asociado.",
        )

    # Z automática: altura del polígono bajo el punto de click.
    # El front siempre manda 0 por defecto (no calcula Z), así que un 0
    # explícito se trata como "sin especificar" y se resuelve acá.
    posicion_z = payload.posicion_z or 0.0
    if not payload.posicion_z:
        modelo2d = PlanoRepository.get_modelo2d_by_id(id_modelo2d)
        if modelo2d:
            posicion_z = get_altura_en_punto(
                modelo2d.get("poligonos") or [],
                payload.posicion_x,
                payload.posicion_y,
                default=0.0,
            )

    radio_cobertura = payload.altura * 2.0

    mastil = MastilRepository.create_mastil(
        id_modelo2d=id_modelo2d,
        id_proyecto=id_proyecto or None,
        posicion_x=payload.posicion_x,
        posicion_y=payload.posicion_y,
        posicion_z=posicion_z,          # ← ya no es siempre 0
        altura=payload.altura,
        tipo=payload.tipo,
        radio_cobertura=radio_cobertura,
    )
    return mastil




@router.get("/modelo3d/{id_modelo3d}", response_model=List[MastilResponse])
def get_mastiles_by_modelo3d(id_modelo3d: str) -> List[Dict[str, Any]]:
    """HU05: Lista todos los mástiles de un Modelo 3D."""
    try:
        modelo3d = Modelo3DRepository.get_modelo3d_by_id(id_modelo3d)
    except Exception:
        # ID inválido (ej. no es UUID): devolver lista vacía en vez de 500
        return []

    if not modelo3d:
        # Modelo no encontrado: lista vacía (no es error fatal en la página de mástiles)
        return []

    return MastilRepository.get_mastiles_by_modelo3d_id(id_modelo3d)


@router.get("/modelo2d/{id_modelo2d}", response_model=List[MastilResponse])
def get_mastiles_by_modelo2d(id_modelo2d: str) -> List[Dict[str, Any]]:
    """HU05: Lista todos los mástiles asociados a un Modelo 2D (via modelo 3D)."""
    return MastilRepository.get_mastiles_by_modelo2d_id(id_modelo2d)


@router.put("/{id}", response_model=MastilResponse)
def update_mastil(id: str, payload: MastilUpdateRequest) -> Dict[str, Any]:
    """HU05: Mueve o actualiza un mástil (coordenadas, altura o tipo)."""
    existing = MastilRepository.get_mastil_by_id(id)
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
        modelo2d = PlanoRepository.get_modelo2d_by_id(id_modelo2d) if id_modelo2d else None

        if modelo2d:
            posicion_z = get_altura_en_punto(
                modelo2d.get("poligonos") or [],
                posicion_x,
                posicion_y,
                default=0.0,
            )

    updated = MastilRepository.update_mastil(
        id_mastil=id,
        posicion_x=payload.posicion_x,
        posicion_y=payload.posicion_y,
        posicion_z=posicion_z,
        altura=payload.altura,
        tipo=payload.tipo,
    ) or existing

    return updated


@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_mastil(id: str) -> Dict[str, Any]:
    """HU05: Elimina un mástil por ID."""
    existing = MastilRepository.get_mastil_by_id(id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el mástil con ID '{id}'.",
        )

    deleted = MastilRepository.delete_mastil(id)
    return {"id": id, "mensaje": "Mástil eliminado exitosamente.", "exito": deleted}


@router.get("/proyecto/{idProyecto}/cobertura", response_model=CoberturaResponse)
def get_cobertura_mastiles(idProyecto: str) -> Dict[str, Any]:
    """HU05: Evalúa la cobertura SPDA para todos los mástiles de un proyecto (Esfera Rodante)."""
    # 1. Nivel de protección (HU04)
    #    Fallback hardcodeado: Nivel I (R = 20 m) cuando aún no hay nivel calculado.
    nivel_str = "Nivel I"
    rolling_radius = 20.0

    try:
        nivel_db = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(idProyecto)
        if nivel_db:
            nivel_str = nivel_db.get("nivel") or nivel_db.get("nivel_proteccion_calculado") or "Nivel I"
            if "Nivel I" in nivel_str and "Nivel II" not in nivel_str:
                rolling_radius = 20.0
            elif "Nivel II" in nivel_str:
                rolling_radius = 30.0
            elif "Nivel III" in nivel_str:
                rolling_radius = 45.0
            elif "Nivel IV" in nivel_str:
                rolling_radius = 60.0
    except Exception:
        # Sin nivel asignado: usar Nivel I como predeterminado
        pass

    # 2. Dimensiones del modelo 3D
    dims = {"longitud": 20.0, "anchura": 15.0, "altura": 7.5}
    try:
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(idProyecto)
        if modelo3d:
            dims = modelo3d.get("geometria_volumetrica", {}).get("dimensiones", dims)
    except Exception:
        pass

    # 3. Mástiles del proyecto
    masts = []
    try:
        masts = MastilRepository.get_mastiles_by_proyecto_id(idProyecto)
    except Exception:
        pass

    # 4. Sin mástiles: devolver respuesta vacía válida
    if not masts:
        return {
            "id_proyecto": idProyecto,
            "nivel_proteccion": nivel_str,
            "radio_esfera_rodante_r": rolling_radius,
            "total_mastiles": 0,
            "mastiles": [],
            "puntos_cobertura": [],
            "puntos_desprotegidos": [],
            "porcentaje_cobertura": 0.0,
            "advertencias": ["Sin mástiles instalados. El edificio no tiene cobertura SPDA."],
        }

    # 5. Convertir al formato esperado por SPDAService
    masts_for_eval = [
        {
            "id": m.get("id"),
            "posicion_x": m.get("posicion_x", 0.0),
            "posicion_y": m.get("posicion_y", 0.0),
            "posicion_z": m.get("posicion_z", 0.0),
            "altura": m.get("altura", 0.0),
            "tipo": m.get("tipo", "Franklin"),
        }
        for m in masts
    ]

    # 6. Evaluación SPDA
    try:
        evaluation = SPDAService.evaluate_masts_coverage(
            masts=masts_for_eval,
            building_dim=dims,
            rolling_sphere_radius=rolling_radius,
        )
    except Exception as e:
        evaluation = {
            "puntos_cobertura": [],
            "puntos_desprotegidos": [],
            "porcentaje_cobertura": 0.0,
            "advertencias": [f"No se pudo evaluar la cobertura: {str(e)}"],
        }

    return {
        "id_proyecto": idProyecto,
        "nivel_proteccion": nivel_str,
        "radio_esfera_rodante_r": rolling_radius,
        "total_mastiles": len(masts),
        "mastiles": masts,
        "puntos_cobertura": evaluation["puntos_cobertura"],
        "puntos_desprotegidos": evaluation["puntos_desprotegidos"],
        "porcentaje_cobertura": evaluation["porcentaje_cobertura"],
        "advertencias": evaluation["advertencias"],
    }

