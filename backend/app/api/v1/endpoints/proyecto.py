from fastapi import APIRouter, HTTPException

from app.repositories.proyecto_repository import ProyectoRepository
from app.schemas.proyecto_schema import ProyectoUbicacionResponse

# NOTA: ajustá el prefix/import paths si en tu proyecto los routers y
# repositorios están en otras carpetas; seguí acá el mismo layout que ya usan
# niveles_proteccion_router.py / nivel_proteccion_repository.py.
router = APIRouter(prefix="/proyectos", tags=["Proyectos"])


@router.get("/{id_proyecto}/ubicacion", response_model=ProyectoUbicacionResponse)
def obtener_ubicacion_proyecto(id_proyecto: str):
    """
    HU04: Devuelve nombre y ubicación del proyecto.

    Se usa en el paso de Nivel de Protección (Anexo B) para mostrar la
    ubicación junto al Ng adoptado, sin tener que pedir el proyecto completo.
    """
    proyecto = ProyectoRepository.get_ubicacion_by_proyecto_id(id_proyecto)
    if not proyecto:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado")
    return proyecto