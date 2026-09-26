import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from fastapi import APIRouter, HTTPException, status
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


def _extraer_dimensiones_modelo3d(modelo3d: Dict[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Extrae longitud, anchura y altura desde el Modelo3D ya generado.

    `geometria_volumetrica` es la metadata que arma
    model3d_generator_service.generar_modelo_3d(...):
        - "bbox": [bx0, by0, bx1, by1]  (bounding box de TODOS los polígonos
          del Modelo2D, en metros) -> longitud/anchura del edificio.
        - "levels": lista ordenada de las cotas de altura (en metros)
          detectadas en el Modelo2D -> se usa el mayor valor como altura H,
          igual que la columna `altura_h` de la tabla modelo3d (se prioriza
          esta última si está presente y es > 0).

    Solo se llama cuando el proyecto todavía no tiene un registro guardado en
    `nivel_de_proteccion` (ver _obtener_dimensiones_y_ng): una vez calculado,
    L/W/H quedan persistidos ahí y se reusan en cálculos posteriores.
    """
    geometria = modelo3d.get("geometria_volumetrica") or {}

    bbox = geometria.get("bbox")
    length = width = None
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        bx0, by0, bx1, by1 = bbox
        length = round(float(bx1) - float(bx0), 2)
        width = round(float(by1) - float(by0), 2)

    height = modelo3d.get("altura_h")
    if not height or float(height) <= 0:
        levels = geometria.get("levels") or []
        alturas = [float(v) for v in levels if v is not None]
        height = max(alturas) if alturas else None

    return length, width, (float(height) if height else None)


def _obtener_dimensiones_y_ng(
    id_proyecto: str,
    id_zona_payload: Optional[str] = None,
    departamento: Optional[str] = None,
) -> Tuple[float, float, float, Optional[str], float]:
    """Obtiene L, W, H y Ng para el cálculo de HU04.

    L/W/H: si el proyecto ya tiene un cálculo previo guardado en
    `nivel_de_proteccion`, se reusan esas dimensiones en lugar de volver a
    leer y parsear el Modelo3D. Si todavía no hay nada guardado, se extraen
    del Modelo3D (bounding box + altura) como primer cálculo.

    Ng: desde la zona ceráunica correspondiente a la ubicación del proyecto.
    """

    # 1. Zona ceráunica / Ng según la localidad real del proyecto
    id_zona = id_zona_payload
    zona = None
    if id_zona:
        zona = NivelProteccionRepository.get_zona_ceraunica_by_id(id_zona)
    if not zona:
        # Ya no se usa "departamento" como string libre: la zona sale de
        # matchear proyecto.localidad contra zona_ceraunica.ciudad.
        zona = NivelProteccionRepository.get_zona_ceraunica_by_departamento(id_proyecto)
        if zona:
            id_zona = str(zona.get("id_zona", zona.get("id", "")))
    density_ng = float(zona.get("ng", zona.get("densidad_rayos_ng", 2.5))) if zona else 2.5

    # 2. Dimensiones: primero se intenta reusar lo ya persistido para el
    #    proyecto; si no hay nada guardado todavía, se extraen del Modelo3D
    #    (bounding box de todos los polígonos + mayor cota detectada).
    length = width = height = None
    dims_guardadas = NivelProteccionRepository.get_dimensiones_by_proyecto_id(id_proyecto)
    if dims_guardadas:
        length = dims_guardadas.get("longitud_edificacion")
        width = dims_guardadas.get("anchura_edificacion")
        height = dims_guardadas.get("altura_edificacion")

    if not length or not width or not height:
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(id_proyecto)
        if modelo3d:
            length, width, height = _extraer_dimensiones_modelo3d(modelo3d)

    if not length or length <= 0:
        length = 20.0
    if not width or width <= 0:
        width = 15.0
    if not height or height <= 0:
        height = 7.5

    return float(length), float(width), float(height), id_zona, density_ng


@router.post("/calcular")
def calcular_nivel_proteccion(payload: NivelProteccionCalcularRequest) -> Dict[str, Any]:
    """HU04: Calcula Ae, Nd, Nc y el Nivel de Protección recomendado (F.1),
    SIN persistir. Lo usa el formulario para previsualizar el resultado cada
    vez que el usuario cambia los factores A-B-C-D-E."""

    length, width, height, id_zona, density_ng = _obtener_dimensiones_y_ng(
        payload.id_proyecto, payload.id_zona, payload.departamento
    )

    risk_result = level_protection_service.calculate_risk(
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
    risk_result["id_zona"] = id_zona
    return risk_result


@router.post("", response_model=NivelProteccionResponse, status_code=status.HTTP_201_CREATED)
def guardar_nivel_proteccion(payload: NivelProteccionCreateRequest) -> Dict[str, Any]:
    """HU04: Recalcula (para consistencia) y guarda el Nivel de Protección,
    respetando el nivel que el usuario haya seleccionado libremente en la
    grilla (nivel_seleccionado). Si no se envía, se guarda el recomendado."""

    length, width, height, id_zona, density_ng = _obtener_dimensiones_y_ng(
        payload.id_proyecto, payload.id_zona, payload.departamento
    )

    risk_result = level_protection_service.calculate_risk(
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

    nivel_recomendado = risk_result["nivel_proteccion_recomendado"]
    nivel_final = payload.nivel_seleccionado or nivel_recomendado
    datos_nivel_final = level_protection_service.datos_nivel(nivel_final)

    saved_db = NivelProteccionRepository.save_nivel_proteccion(
        id_proyecto=payload.id_proyecto,
        id_zona=id_zona,
        nivel_proteccion=nivel_final,
        nivel_proteccion_recomendado=nivel_recomendado,
        nd=risk_result["frecuencia_impactos_nd"],
        nc=risk_result["frecuencia_tolerable_nc"],
        ae=risk_result["area_equivalente_ae"],
        eficiencia_minima=risk_result["eficiencia_proteccion"],
        radio_esfera=datos_nivel_final["radio_esfera_r"],
        factor_a_e=risk_result["factores_riesgo"],  # dict {a,b,c,d,e} -> JSONB
        margen_lateral=risk_result["margen_lateral"],
        longitud_edificacion=length,
        anchura_edificacion=width,
        altura_edificacion=height,
    )

    id_np = str(saved_db.get("id_nivel_proteccion", saved_db.get("id", "")))

    return {
        "id_nivel_proteccion": id_np,
        "id_proyecto": str(saved_db.get("id_proyecto", payload.id_proyecto)),
        "id_zona": str(saved_db.get("id_zona")) if saved_db.get("id_zona") else None,
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
def get_nivel_proteccion_by_proyecto(idProyecto: str) -> Dict[str, Any]:
    """HU04: Retrieve previously calculated SPDA protection level for a
    project. Todo sale directo de la fila guardada (L/W/H, factores A-E,
    nivel seleccionado y nivel recomendado), no hace falta volver a
    consultar el Modelo3D."""
    record = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(idProyecto)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se ha realizado el cálculo de Nivel de Protección para el proyecto '{idProyecto}'.",
        )

    id_np = str(record.get("id_nivel_proteccion", record.get("id", "")))
    nd = record.get("nd", 0.0)
    nc = record.get("nc", 0.0)
    margen_lateral = record.get("margen_lateral", 3)

    factores_riesgo = record.get("factor_a_e") or {}
    if isinstance(factores_riesgo, str):
        factores_riesgo = json.loads(factores_riesgo)

    # requiere_spcr se recalcula con la misma función canónica del F.1 (a
    # partir de nd/nc ya guardados) en vez de reimplementar la comparación acá.
    recomendacion = determine_nivel_recomendado(nd, nc)

    return {
        "id_nivel_proteccion": id_np,
        "id_proyecto": str(record.get("id_proyecto", idProyecto)),
        "id_zona": str(record.get("id_zona")) if record.get("id_zona") else None,
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