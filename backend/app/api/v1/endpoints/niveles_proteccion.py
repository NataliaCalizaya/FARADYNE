from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, status
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.schemas.nivel_proteccion_schema import (
    NivelProteccionCreateRequest,
    NivelProteccionResponse,
)
from app.services.spda_service import SPDAService

router = APIRouter(prefix="/niveles-proteccion", tags=["HU04 - Nivel de Protección SPDA"])


@router.post("", response_model=NivelProteccionResponse, status_code=status.HTTP_201_CREATED)
def calculate_and_save_nivel_proteccion(payload: NivelProteccionCreateRequest) -> Dict[str, Any]:
    """HU04: Calculate SPDA lightning protection risk level (Ae, Nd, Nc) per IEC 62305 / IRAM 2184."""
    # 1. Fetch zona_ceraunica
    id_zona = payload.id_zona
    zona = None
    if id_zona:
        zona = NivelProteccionRepository.get_zona_ceraunica_by_id(id_zona)

    if not zona:
        dept = payload.departamento or "Lima"
        zona = NivelProteccionRepository.get_zona_ceraunica_by_departamento(dept)
        if zona:
            id_zona = str(zona.get("id_zona", zona.get("id", "")))

    density_ng = float(zona.get("ng", zona.get("densidad_rayos_ng", 2.5))) if zona else 2.5

    # 2. Determine building dimensions L, W, H
    length = payload.longitud_edificacion
    width = payload.anchura_edificacion
    height = payload.altura_edificacion

    if length is None or width is None or height is None:
        # Fetch dimensions from associated modelo3d if available
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(payload.id_proyecto)
        if modelo3d:
            dims = modelo3d.get("geometria_volumetrica", {}).get("dimensiones", {})
            if length is None:
                length = float(dims.get("longitud", 20.0))
            if width is None:
                width = float(dims.get("anchura", 15.0))
            if height is None:
                height = float(dims.get("altura", 7.5))

    if length is None or length <= 0:
        length = 20.0
    if width is None or width <= 0:
        width = 15.0
    if height is None or height <= 0:
        height = 7.5

    # 3. Calculate risk parameters
    risk_result = SPDAService.calculate_risk(
        length=length,
        width=width,
        height=height,
        density_ng=density_ng,
        factor_cd=payload.factor_ubicacion_cd,
        factor_cb=payload.factor_estructura_cb,
        factor_cc=payload.factor_contenido_cc,
        factor_ce=payload.factor_lineas_ce,
    )

    # 4. Save to database table 'nivel_de_proteccion'
    saved_db = NivelProteccionRepository.save_nivel_proteccion(
        id_proyecto=payload.id_proyecto,
        id_zona=id_zona,
        longitud=length,
        anchura=width,
        altura=height,
        area_ae=risk_result["area_equivalente_ae"],
        nd=risk_result["frecuencia_impactos_nd"],
        nc=risk_result["frecuencia_tolerable_nc"],
        requiere_spcr=risk_result["requiere_spcr"],
        nivel_calculado=risk_result["nivel_proteccion_calculado"],
        eficiencia=risk_result["eficiencia_proteccion"],
        radio_esfera=risk_result["radio_esfera_rodante_r"],
        factores_riesgo=risk_result["factores_riesgo"],
    )

    id_np = str(saved_db.get("id_nivel_proteccion", saved_db.get("id", "")))

    return {
        "id": id_np,
        "id_proyecto": str(saved_db.get("id_proyecto", payload.id_proyecto)),
        "id_zona": str(saved_db.get("id_zona")) if saved_db.get("id_zona") else None,
        "longitud_edificacion": length,
        "anchura_edificacion": width,
        "altura_edificacion": height,
        "area_equivalente_ae": saved_db.get("ae", risk_result["area_equivalente_ae"]),
        "frecuencia_impactos_nd": saved_db.get("nd", risk_result["frecuencia_impactos_nd"]),
        "frecuencia_tolerable_nc": saved_db.get("nc", risk_result["frecuencia_tolerable_nc"]),
        "requiere_spcr": risk_result["requiere_spcr"],
        "nivel_proteccion_calculado": saved_db.get("nivel", risk_result["nivel_proteccion_calculado"]),
        "eficiencia_proteccion": saved_db.get("eficiencia_minima", risk_result["eficiencia_proteccion"]),
        "factores_riesgo": risk_result.get("factores_riesgo", {}),
        "fecha_calculo": datetime.now(),
    }


@router.get("/{idProyecto}", response_model=NivelProteccionResponse)
def get_nivel_proteccion_by_proyecto(idProyecto: str) -> Dict[str, Any]:
    """HU04: Retrieve previously calculated SPDA protection level for a project."""
    record = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(idProyecto)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se ha realizado el cálculo de Nivel de Protección para el proyecto '{idProyecto}'.",
        )

    id_np = str(record.get("id_nivel_proteccion", record.get("id", "")))

    return {
        "id": id_np,
        "id_proyecto": str(record.get("id_proyecto", idProyecto)),
        "id_zona": str(record.get("id_zona")) if record.get("id_zona") else None,
        "longitud_edificacion": record.get("longitud_edificacion", 20.0),
        "anchura_edificacion": record.get("anchura_edificacion", 15.0),
        "altura_edificacion": record.get("altura_edificacion", 7.5),
        "area_equivalente_ae": record.get("ae", 0.0),
        "frecuencia_impactos_nd": record.get("nd", 0.0),
        "frecuencia_tolerable_nc": record.get("nc", 0.0),
        "requiere_spcr": bool(record.get("nd", 0) > record.get("nc", 0)) if record.get("nc") else True,
        "nivel_proteccion_calculado": record.get("nivel", "II"),
        "eficiencia_proteccion": record.get("eficiencia_minima", 0.95),
        "factores_riesgo": record.get("factores_riesgo", {}),
        "fecha_calculo": datetime.now(),
    }

