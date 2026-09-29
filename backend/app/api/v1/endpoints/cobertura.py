from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, status
from app.services.spda_service import SPDAService
from app.api.v1.endpoints.mastiles import _extraer_dimensiones_modelo3d
from app.repositories.nivel_proteccion_repository import NivelProteccionRepository
from app.repositories.plano_repository import PlanoRepository  # nuevo import
from app.repositories.mastil_repository import MastilRepository
from app.repositories.modelo3d_repository import Modelo3DRepository

from app.schemas.mastil_schema import (
    CoberturaResponse,
)
RADIOS_POR_NIVEL = {"Nivel IV": 60.0, "Nivel III": 45.0, "Nivel II": 30.0, "Nivel I": 20.0}


router = APIRouter(prefix="/cobertura", tags=["cobertura de mastiles"])

def _radio_por_nivel(nivel_str: str) -> float:
    # Orden importante: "Nivel I" está contenido en "Nivel II/III".
    for clave, radio in RADIOS_POR_NIVEL.items():
        if clave in nivel_str:
            return radio
    return 20.0


@router.get("/proyecto/{idProyecto}", response_model=CoberturaResponse)
def get_cobertura_mastiles(idProyecto: str) -> Dict[str, Any]:
    """HU05: Cobertura SPDA por ternas de mástiles (Esfera Rodante)."""
    nivel_str, rolling_radius = "Nivel I", 20.0
    try:
        nivel_db = NivelProteccionRepository.get_nivel_proteccion_by_proyecto_id(idProyecto)
        if nivel_db:
            nivel_str = (
                nivel_db.get("nivel_proteccion")
                or nivel_db.get("nivel_proteccion_recomendado")
                or "Nivel I"
            )
            rolling_radius = _radio_por_nivel(nivel_str)
    except Exception:
        pass

    dims = {"longitud": 20.0, "anchura": 15.0, "altura": 7.5}
    poligonos = []
    try:
        modelo3d = Modelo3DRepository.get_modelo3d_by_proyecto_id(idProyecto)
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
        pass

    masts = []
    try:
        masts = MastilRepository.get_mastiles_by_proyecto_id(idProyecto)
    except Exception:
        pass

    base = {
        "id_proyecto": idProyecto,
        "nivel_proteccion": nivel_str,
        "radio_esfera_rodante_r": rolling_radius,
        "total_mastiles": len(masts),
        "mastiles": masts,
    }

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

    try:
        ev = SPDAService.evaluate_masts_coverage(
            masts=masts_for_eval,
            building_dim=dims,
            rolling_sphere_radius=rolling_radius,
            poligonos=poligonos,
        )
    except Exception as e:
        ev = {"porcentaje_cobertura": 0.0, "advertencias": [f"No se pudo evaluar la cobertura: {e}"]}

    return {
        **base,
        "superficies_esfera": ev.get("superficies_esfera", []),
        "triangulos_sin_esfera": ev.get("triangulos_sin_esfera", []),
        "zonas_desprotegidas": ev.get("zonas_desprotegidas", []),
        "puntos_cobertura": ev.get("puntos_cobertura", []),
        "puntos_desprotegidos": ev.get("puntos_desprotegidos", []),
        "porcentaje_cobertura": ev["porcentaje_cobertura"],
        "advertencias": ev["advertencias"],
    }