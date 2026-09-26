from typing import Optional
from pydantic import BaseModel

class ProyectoUbicacionResponse(BaseModel):
    """HU04: respuesta de GET /proyectos/{id_proyecto}/ubicacion.

    Se pide de forma acotada (no el proyecto entero) porque lo único que
    necesita el paso de Nivel de Protección es nombre + ubicación, para
    mostrarlos junto al Ng adoptado (Paso 1)."""

    id_proyecto: str
    nombre: str
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None

    class Config:
        from_attributes = True