from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session
from fastapi import Depends
from app.core.database import get_db
from app.repositories.zona_ceraunica_repository import ZonaCeraunicaRepository

router = APIRouter(prefix="/zonas-ceraunicas", tags=["Zonas Ceráunicas"])



@router.get("/localidades", response_model=List[str])
def buscar_localidades(
    q: str = Query(..., min_length=1, description="Prefijo a buscar, ej: 'M'"),
    db: Session = Depends(get_db),
) -> List[str]:
    """Autocomplete de localidades para el campo 'Localidad' del formulario
    de Datos del Proyecto. Devuelve ciudades de `zona_ceraunica` que
    empiezan con `q`."""
    return ZonaCeraunicaRepository.buscar_localidades(db, q)


@router.get("/by-localidad/{localidad}")
def obtener_ng_por_localidad(localidad: str, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Devuelve el Ng (densidad de descargas a tierra) de la zona ceráunica
    cuya ciudad coincide exactamente con `localidad`. 404 si no hay match."""
    zona = ZonaCeraunicaRepository.get_ng_by_localidad(db, localidad)
    if not zona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró una zona ceráunica para la localidad '{localidad}'.",
        )
    return {
        "id_zona": str(zona["id_zona"]),
        "ciudad": zona["ciudad"],
        "ng": zona["ng"],
    }