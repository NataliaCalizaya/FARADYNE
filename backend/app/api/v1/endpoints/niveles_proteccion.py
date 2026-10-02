import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.common import extraer_dimensiones_modelo3d, to_int
from app.core.database import get_db
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.schemas.nivel_proteccion_schema import (
    NivelProteccionCalcularRequest,
    NivelProteccionCreateRequest,
    NivelProteccionResponse,
)
from app.services.level_protection_service import (
    determine_nivel_recomendado,
    formula_ae_por_margen,
    level_protection_service,
)

router = APIRouter(prefix="/niveles-proteccion", tags=["HU04 - Nivel de Protección SPDA"])


def _obtener_dimensiones_y_ng(
    db: Session,
    id_proyecto: int,
    id_zona_payload: Optional[Any] = None,
) -> Tuple[float, float, float, Optional[int], float]:
    """L, W, H y Ng para el cálculo de HU04.

    Ng: zona indicada en el payload o, si no, la que sale de matchear
    proyecto.localidad contra zona_ceraunica.ciudad.
    L/W/H: se reusan las ya persistidas en `nivel_de_proteccion`; si no hay
    cálculo previo, se extraen del Modelo3D (bbox + altura).
    """
    proyecto = NivelProteccionRepository.get_proyecto_by_id(db, id_proyecto)
    if not proyecto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el proyecto '{id_proyecto}'.",
        )

    # 1. Zona ceráunica / Ng
    zona = None
    if id_zona_payload not in (None, ""):
        zona = NivelProteccionRepository.get_zona_ceraunica_by_id(
            db, to_int(id_zona_payload, "id_zona")
        )
    if not zona:
        zona = NivelProteccionRepository.get_zona_ceraunica_by_departamento(db, id_proyecto)
    if not zona:
        # El repository indica que NO se debe inventar un Ng: se informa el error.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "La localidad del proyecto no coincide con ninguna zona ceráunica. "
                "Corrija la localidad para obtener el Ng."
            ),
        )
    id_zona = zona.get("id_zona")
    density_ng = float(zona.get("ng"))

    # 2. Dimensiones
    length = width = height = None
    dims_guardadas = NivelProteccionRepository.get_dimensiones_by_proyecto_id(db, id_proyecto)
    if dims_guardadas:
        length = dims_guardadas.get("longitud_edificacion")
        width = dims_guardadas.get("anchura_edificacion")
        height = dims_guardadas.get("altura_edificacion")

    if not length or not width or not height:
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(db, id_proyecto)
        if modelo3d:
            length, width, height = extraer_dimensiones_modelo3d(modelo3d)

    if not length or length <= 0:
        length = 20.0
    if not width or width <= 0:
        width = 15.0
    if not height or height <= 0:
        height = 7.5

    return float(length), float(width), float(height), id_zona, density_ng


def _calcular_riesgo(payload, length, width, height, density_ng) -> Dict[str, Any]:
    return level_protection_service.calculate_risk(
        length=length,
        width=width,
        height=height,
        density_ng=density_ng,
        factor_a=payload.factor_a,
        factor_b=payload.factor_b,
        factor_c=payload.factor_c,
        factor_d=payload.factor_d,
        factor_e=payload.factor_e,
    )


@router.post("/calcular")
def calcular_nivel_proteccion(
    payload: NivelProteccionCalcularRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HU04: calcula Ae, Nd, Nc y el Nivel recomendado (F.1) SIN persistir."""
    id_proyecto = to_int(payload.id_proyecto, "id_proyecto")
    length, width, height, id_zona, density_ng = _obtener_dimensiones_y_ng(
        db, id_proyecto, payload.id_zona
    )
    risk_result = _calcular_riesgo(payload, length, width, height, density_ng)
    risk_result["id_zona"] = str(id_zona) if id_zona is not None else None
    return risk_result


@router.post("", response_model=NivelProteccionResponse, status_code=status.HTTP_201_CREATED)
def guardar_nivel_proteccion(
    payload: NivelProteccionCreateRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HU04: recalcula y guarda el Nivel de Protección, respetando el nivel
    elegido en la grilla (nivel_seleccionado); si no viene, guarda el recomendado."""
    id_proyecto = to_int(payload.id_proyecto, "id_proyecto")
    length, width, height, id_zona, density_ng = _obtener_dimensiones_y_ng(
        db, id_proyecto, payload.id_zona
    )
    risk_result = _calcular_riesgo(payload, length, width, height, density_ng)

    nivel_recomendado = risk_result["nivel_proteccion_recomendado"]
    nivel_final = payload.nivel_seleccionado or nivel_recomendado
    datos_nivel_final = level_protection_service.datos_nivel(nivel_final)

    saved_db = NivelProteccionRepository.save_nivel_proteccion(
        db,
        id_proyecto=id_proyecto,
        id_zona=id_zona,  # int (FK), no str
        nivel_proteccion=nivel_final,
        nivel_proteccion_recomendado=nivel_recomendado,
        nd=risk_result["frecuencia_impactos_nd"],
        nc=risk_result["frecuencia_tolerable_nc"],
        ae=risk_result["area_equivalente_ae"],
        eficiencia_minima=risk_result["eficiencia_proteccion"],
        radio_esfera=datos_nivel_final["radio_esfera_r"],
        factor_a_e=risk_result["factores_riesgo"],
        margen_lateral=risk_result["margen_lateral"],
        longitud_edificacion=length,
        anchura_edificacion=width,
        altura_edificacion=height,
    )

    id_np = str(saved_db.get("id_nivel_proteccion", saved_db.get("id", "")))

    return {
        "id_nivel_proteccion": id_np,
        "id_proyecto": str(saved_db.get("id_proyecto", id_proyecto)),
        "id_zona": str(saved_db["id_zona"]) if saved_db.get("id_zona") else None,
        "longitud_edificacion": saved_db.get("longitud_edificacion", length),
        "anchura_edificacion": saved_db.get("anchura_edificacion", width),
        "altura_edificacion": saved_db.get("altura_edificacion", height),
        "margen_lateral": saved_db.get("margen_lateral", risk_result["margen_lateral"]),
        "formula_area_utilizada": risk_result["formula_area_utilizada"],
        "area_equivalente_ae": saved_db.get("ae", risk_result["area_equivalente_ae"]),
        "frecuencia_impactos_nd": saved_db.get("nd", risk_result["frecuencia_impactos_nd"]),
        "frecuencia_tolerable_nc": saved_db.get("nc", risk_result["frecuencia_tolerable_nc"]),
        "requiere_spcr": risk_result["requiere_spcr"],
        "nivel_proteccion_recomendado": saved_db.get("nivel_proteccion_recomendado", nivel_recomendado),
        "nivel_proteccion_seleccionado": saved_db.get("nivel_proteccion", nivel_final),
        "eficiencia_proteccion": saved_db.get("eficiencia_minima", risk_result["eficiencia_proteccion"]),
        "radio_esfera_rodante_r": saved_db.get("radio_esfera", datos_nivel_final["radio_esfera_r"]),
        "factores_riesgo": saved_db.get("factor_a_e", risk_result.get("factores_riesgo", {})),
        "fecha_calculo": datetime.now(),
    }


@router.get("/{idProyecto}", response_model=NivelProteccionResponse)
def get_nivel_proteccion_by_proyecto(
    idProyecto: int, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """HU04: cálculo guardado del proyecto; todo sale de la fila persistida."""
    record = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(db, idProyecto)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se ha realizado el cálculo de Nivel de Protección para el proyecto '{idProyecto}'.",
        )

    id_np = str(record.get("id_nivel_proteccion", record.get("id", "")))
    nd = float(record.get("nd") or 0.0)  # columnas Numeric -> Decimal
    nc = float(record.get("nc") or 0.0)
    margen_lateral = record.get("margen_lateral", 3)

    factores_riesgo = record.get("factor_a_e") or {}
    if isinstance(factores_riesgo, str):
        factores_riesgo = json.loads(factores_riesgo)

    recomendacion = determine_nivel_recomendado(nd, nc)

    return {
        "id_nivel_proteccion": id_np,
        "id_proyecto": str(record.get("id_proyecto", idProyecto)),
        "id_zona": str(record["id_zona"]) if record.get("id_zona") else None,
        "longitud_edificacion": record.get("longitud_edificacion", 20.0),
        "anchura_edificacion": record.get("anchura_edificacion", 15.0),
        "altura_edificacion": record.get("altura_edificacion", 7.5),
        "margen_lateral": margen_lateral,
        "formula_area_utilizada": formula_ae_por_margen(margen_lateral),
        "area_equivalente_ae": record.get("ae", 0.0),
        "frecuencia_impactos_nd": nd,
        "frecuencia_tolerable_nc": nc,
        "requiere_spcr": recomendacion["requiere_spcr"],
        "nivel_proteccion_recomendado": record.get("nivel_proteccion_recomendado", recomendacion["nivel_recomendado"]),
        "nivel_proteccion_seleccionado": record.get("nivel_proteccion", "IV"),
        "eficiencia_proteccion": record.get("eficiencia_minima"),
        "radio_esfera_rodante_r": record.get("radio_esfera", 60.0),
        "factores_riesgo": factores_riesgo,
        "fecha_calculo": datetime.now(),
    }
