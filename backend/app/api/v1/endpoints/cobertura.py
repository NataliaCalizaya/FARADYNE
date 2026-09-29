"""app.routers.cobertura_spda

HU05 - Cobertura SPDA por Esfera Rodante (ternas de mástiles).

  GET  /cobertura/proyecto/{idProyecto}          calcula y devuelve (no guarda)
  POST /cobertura/proyecto/{idProyecto}/guardar  calcula, guarda en
                                                 `resultado_simulacion` y devuelve
"""

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, HTTPException, status

from app.repositories.mastil_repository import MastilRepository
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.repositories.plano_repository import PlanoRepository
from app.repositories.resultado_simulacion_repository import ResultadoSimulacionRepository
from app.schemas.cobertura_schema import CoberturaResponse
from app.services.spda_service import SPDAService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cobertura", tags=["cobertura de mastiles"])

# Orden importante: "Nivel I" está contenido en "Nivel II/III".
RADIOS_POR_NIVEL = {"Nivel IV": 60.0, "Nivel III": 45.0, "Nivel II": 30.0, "Nivel I": 20.0}


def _radio_por_nivel(nivel_str: str) -> float:
    for clave, radio in RADIOS_POR_NIVEL.items():
        if clave in nivel_str:
            return radio
    return 20.0


def _extraer_dimensiones_modelo3d(
    modelo3d: Dict[str, Any],
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Longitud, anchura y altura desde `geometria_volumetrica` (bbox / levels)."""
    geometria = modelo3d.get("geometria_volumetrica") or {}

    length = width = None
    bbox = geometria.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        bx0, by0, bx1, by1 = bbox
        length = round(float(bx1) - float(bx0), 2)
        width = round(float(by1) - float(by0), 2)

    height = modelo3d.get("altura_h")
    if not height or float(height) <= 0:
        alturas = [float(v) for v in (geometria.get("levels") or []) if v is not None]
        height = max(alturas) if alturas else None

    return length, width, (float(height) if height else None)


def _calcular_cobertura(id_proyecto: str) -> Dict[str, Any]:
    """Calcula la cobertura del proyecto. Devuelve la respuesta + `_evaluacion` (interno)."""
    # 1. Nivel de protección (HU04) -> radio de la esfera. Fallback: Nivel I (20 m).
    nivel_str, radio = "Nivel I", 20.0
    try:
        nivel_db = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(id_proyecto)
        if nivel_db:
            nivel_str = (
                nivel_db.get("nivel_proteccion")
                or nivel_db.get("nivel_proteccion_recomendado")
                or nivel_db.get("nivel")
                or "Nivel I"
            )
            radio = _radio_por_nivel(nivel_str)
    except Exception:
        logger.exception("No se pudo leer el nivel de protección del proyecto %s", id_proyecto)

    # 2. Modelo 3D (dimensiones de respaldo) + polígonos del Modelo 2D (cubierta real).
    dims = {"longitud": 20.0, "anchura": 15.0, "altura": 7.5}
    poligonos = []
    try:
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(id_proyecto)
        if modelo3d:
            length, width, height = _extraer_dimensiones_modelo3d(modelo3d)
            dims = {
                "longitud": length or dims["longitud"],
                "anchura": width or dims["anchura"],
                "altura": height or dims["altura"],
            }
            id_modelo2d = modelo3d.get("id_modelo2d")
            modelo2d = PlanoRepository.get_modelo2d_by_id(id_modelo2d) if id_modelo2d else None
            poligonos = (modelo2d or {}).get("poligonos") or []
    except Exception:
        logger.exception("No se pudo leer el modelo del proyecto %s", id_proyecto)

    # 3. Mástiles del proyecto.
    masts = []
    try:
        masts = MastilRepository.get_mastiles_by_proyecto_id(id_proyecto)
    except Exception:
        logger.exception("No se pudieron leer los mástiles del proyecto %s", id_proyecto)

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

    # 4. Evaluación.
    try:
        evaluacion = SPDAService.evaluate_masts_coverage(
            masts=masts_for_eval,
            building_dim=dims,
            rolling_sphere_radius=radio,
            poligonos=poligonos,
        )
        evaluacion_ok = True
    except Exception as e:
        logger.exception("Falló la evaluación de cobertura del proyecto %s", id_proyecto)
        evaluacion = {"porcentaje_cobertura": 0.0, "advertencias": [f"No se pudo evaluar la cobertura: {e}"]}
        evaluacion_ok = False

    respuesta = {
        "id_proyecto": id_proyecto,
        "nivel_proteccion": nivel_str,
        "radio_esfera_rodante_r": radio,
        "total_mastiles": len(masts),
        "mastiles": masts,
        "superficies_esfera": evaluacion.get("superficies_esfera", []),
        "triangulos_sin_esfera": evaluacion.get("triangulos_sin_esfera", []),
        "zonas_desprotegidas": evaluacion.get("zonas_desprotegidas", []),
        "prismas": evaluacion.get("prismas", []),
        "puntos_cobertura": evaluacion.get("puntos_cobertura", []),
        "puntos_desprotegidos": evaluacion.get("puntos_desprotegidos", []),
        "porcentaje_cobertura": evaluacion["porcentaje_cobertura"],
        "advertencias": evaluacion["advertencias"],
    }
    return {"respuesta": respuesta, "evaluacion": evaluacion, "evaluacion_ok": evaluacion_ok}


@router.get("/proyecto/{idProyecto}", response_model=CoberturaResponse)
def get_cobertura_mastiles(idProyecto: str) -> Dict[str, Any]:
    """HU05: cobertura SPDA por ternas de mástiles (no persiste)."""
    return _calcular_cobertura(idProyecto)["respuesta"]


@router.post("/proyecto/{idProyecto}/guardar", response_model=CoberturaResponse)
def guardar_cobertura_mastiles(idProyecto: str) -> Dict[str, Any]:
    """HU05: recalcula la cobertura y guarda qué prismas quedan protegidos/vulnerables."""
    calculo = _calcular_cobertura(idProyecto)
    if not calculo["evaluacion_ok"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo evaluar la cobertura; no se guardó el resultado.",
        )

    protegidas, vulnerables, mallas = SPDAService.resumen_para_persistencia(calculo["evaluacion"])
    try:
        fila = ResultadoSimulacionRepository.upsert_por_proyecto(
            idProyecto, protegidas, vulnerables, mallas
        )
    except Exception:
        logger.exception("No se pudo guardar el resultado de cobertura del proyecto %s", idProyecto)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo guardar el resultado de cobertura en la base de datos.",
        )

    respuesta = calculo["respuesta"]
    respuesta["guardado"] = True
    respuesta["fecha_simulacion"] = fila.get("fecha_simulacion")
    return respuesta