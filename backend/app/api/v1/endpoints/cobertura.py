"""app.routers.cobertura_spda

HU05 - Cobertura SPDA por Esfera Rodante (ternas de mástiles).

  GET  /cobertura/proyecto/{idProyecto}          calcula y devuelve (no guarda)
  POST /cobertura/proyecto/{idProyecto}/guardar  calcula, guarda en
                                                 `resultado_simulacion` y devuelve

Superficies devueltas: parches (ternas), uniones (banda entre ternas
vecinas), faldas y casquetes (cierre del borde hasta el suelo).
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.endpoints.common import extraer_dimensiones_modelo3d
from app.core.database import get_db
from app.repositories.mastil_repository import MastilRepository
from app.repositories.modelo3d_repository import Modelo3DRepository
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.repositories.plano_repository import PlanoRepository
from app.repositories.resultado_simulacion_repository import ResultadoSimulacionRepository
from app.schemas.cobertura_schema import CoberturaResponse
from app.services.spda_service import SPDAService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cobertura", tags=["cobertura de mastiles"])

# La BD guarda solo 'I' | 'II' | 'III' | 'IV' (CHECK); se acepta también "Nivel IV".
RADIOS_POR_NIVEL = {"IV": 60.0, "III": 45.0, "II": 30.0, "I": 20.0}


def _radio_por_nivel(nivel_str: str) -> float:
    clave = str(nivel_str).upper().replace("NIVEL", "").strip()
    return RADIOS_POR_NIVEL.get(clave, 20.0)


def _calcular_cobertura(db: Session, id_proyecto: int) -> Dict[str, Any]:
    """Calcula la cobertura del proyecto. Devuelve respuesta + evaluación (interno)."""
    # 1. Nivel de protección (HU04) -> radio de la esfera. Fallback: Nivel I (20 m).
    nivel_str, radio = "I", 20.0
    try:
        nivel_db = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(db, id_proyecto)
        if nivel_db:
            nivel_str = (
                nivel_db.get("nivel_proteccion")
                or nivel_db.get("nivel_proteccion_recomendado")
                or "I"
            )
            radio_db = nivel_db.get("radio_esfera")
            radio = float(radio_db) if radio_db else _radio_por_nivel(nivel_str)
    except Exception:
        db.rollback()  # una query fallida deja la transacción abortada
        logger.exception("No se pudo leer el nivel de protección del proyecto %s", id_proyecto)

    # 2. Modelo 3D (dimensiones de respaldo) + polígonos del Modelo 2D.
    dims = {"longitud": 20.0, "anchura": 15.0, "altura": 7.5}
    poligonos = []
    try:
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(db, id_proyecto)
        if modelo3d:
            length, width, height = extraer_dimensiones_modelo3d(modelo3d)
            dims = {
                "longitud": length or dims["longitud"],
                "anchura": width or dims["anchura"],
                "altura": height or dims["altura"],
            }
            id_modelo2d = modelo3d.get("id_modelo2d")
            modelo2d = PlanoRepository.get_modelo2d_by_id(db, id_modelo2d) if id_modelo2d else None
            poligonos = (modelo2d or {}).get("poligonos") or []
    except Exception:
        db.rollback()
        logger.exception("No se pudo leer el modelo del proyecto %s", id_proyecto)

    # 3. Mástiles del proyecto.
    masts = []
    try:
        masts = MastilRepository.get_mastiles_by_proyecto_id(db, id_proyecto)
    except Exception:
        db.rollback()
        logger.exception("No se pudieron leer los mástiles del proyecto %s", id_proyecto)

    # El service calcula la punta como posicion_z + altura.
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

    # 4. Evaluación (parches + uniones + faldas/casquetes + muestreo de cubierta).
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
        "id_proyecto": str(id_proyecto),
        "nivel_proteccion": nivel_str,
        "radio_esfera_rodante_r": radio,
        "total_mastiles": len(masts),
        "mastiles": masts,
        "superficies_esfera": evaluacion.get("superficies_esfera", []),
        "triangulos_sin_esfera": evaluacion.get("triangulos_sin_esfera", []),
        "uniones_sin_superficie": evaluacion.get("uniones_sin_superficie", []),
        "zonas_desprotegidas": evaluacion.get("zonas_desprotegidas", []),
        "prismas": evaluacion.get("prismas", []),
        "puntos_cobertura": evaluacion.get("puntos_cobertura", []),
        "puntos_desprotegidos": evaluacion.get("puntos_desprotegidos", []),
        "porcentaje_cobertura": evaluacion["porcentaje_cobertura"],
        "area_total_m2": evaluacion.get("area_total_m2", 0.0),
        "area_protegida_m2": evaluacion.get("area_protegida_m2", 0.0),
        "paso_malla_m": evaluacion.get("paso_malla_m"),
        "advertencias": evaluacion["advertencias"],
    }
    return {"respuesta": respuesta, "evaluacion": evaluacion, "evaluacion_ok": evaluacion_ok}


@router.get("/proyecto/{idProyecto}", response_model=CoberturaResponse)
def get_cobertura_mastiles(idProyecto: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """HU05: cobertura SPDA por ternas de mástiles (no persiste)."""
    return _calcular_cobertura(db, idProyecto)["respuesta"]


@router.post("/proyecto/{idProyecto}/guardar", response_model=CoberturaResponse)
def guardar_cobertura_mastiles(idProyecto: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """HU05: recalcula la cobertura y guarda qué prismas quedan protegidos/vulnerables."""
    calculo = _calcular_cobertura(db, idProyecto)
    if not calculo["evaluacion_ok"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo evaluar la cobertura; no se guardó el resultado.",
        )

    # (zonas_protegidas, zonas_vulnerables, mallas_cobertura); las mallas van sin
    # vértices/triángulos (se regeneran con los mástiles y R).
    protegidas, vulnerables, mallas = SPDAService.resumen_para_persistencia(calculo["evaluacion"])
    try:
        fila = ResultadoSimulacionRepository.upsert_por_proyecto(
            db, idProyecto, protegidas, vulnerables, mallas
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