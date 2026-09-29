from typing import Optional
from pydantic import BaseModel
from datetime import date


class ProyectoUbicacionResponse(BaseModel):
    """HU04: respuesta de GET /proyectos/{id_proyecto}/ubicacion.

    Se pide de forma acotada (no el proyecto entero) porque lo único que
    necesita el paso de Nivel de Protección es nombre + ubicación, para
    mostrarlos junto al Ng adoptado (Paso 1).
    """

    id_proyecto: str
    nombre: str
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None

    class Config:
        from_attributes = True


class ProyectoCompletoResponse(BaseModel):
    """GET /proyectos/{id}/completo — devuelve datos del proyecto más los IDs
    derivados resueltos via JOIN (id_plano, id_modelo2d, id_modelo3d) y el
    flag geometria_validada, para reconstruir el estado del frontend al abrir
    una URL directa (F5 o enlace compartido con colaboradores).
    """

    id_proyecto: str
    nombre: str
    cliente: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    estado: str = "borrador"
    fecha_creacion: Optional[date] = None
    fecha_del_proyecto: Optional[date] = None
    # IDs derivados — None si el proyecto aún no tiene ese artefacto
    id_plano: Optional[str] = None
    id_modelo2d: Optional[str] = None
    id_modelo3d: Optional[str] = None
    geometria_validada: bool = False

    class Config:
        from_attributes = True
