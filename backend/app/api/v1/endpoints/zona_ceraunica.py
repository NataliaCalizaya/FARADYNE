from typing import List
from fastapi import APIRouter, Query

from app.repositories.zona_ceraunica_repository import ZonaCeraunicaRepository

router = APIRouter(prefix="/zonas-ceraunicas", tags=["Zonas Ceráunicas"])


@router.get("/localidades", response_model=List[str])
def buscar_localidades(
    q: str = Query(..., min_length=1, description="Prefijo a buscar, ej: 'M'")
) -> List[str]:
    """Autocomplete de localidades para el campo 'Localidad' del formulario
    de Datos del Proyecto. Devuelve ciudades de `zona_ceraunica` que
    empiezan con `q`."""
    return ZonaCeraunicaRepository.buscar_localidades(q)
