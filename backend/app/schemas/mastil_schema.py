from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MastilCreateRequest(BaseModel):
    """Payload para crear un mástil captor.
    
    Se acepta `id_modelo3d` directamente, o bien `id_modelo2d` para que el
    endpoint resuelva automáticamente el modelo 3D asociado.
    """
    id_modelo3d: Optional[str] = Field(None, description="ID del modelo 3D al que pertenece el mástil")
    id_modelo2d: Optional[str] = Field(None, description="ID del modelo 2D (alternativa: el endpoint resuelve el modelo 3D)")
    id_proyecto: Optional[str] = Field(None, description="ID del proyecto")
    posicion_x: float = Field(..., description="Coordenada X en el plano del Modelo2D (metros)")
    posicion_y: float = Field(..., description="Coordenada Y en el plano del Modelo2D (metros)")
    posicion_z: float = Field(0.0, description="Coordenada Z de la base del mástil (metros)")
    altura: float = Field(..., description="Altura h del mástil (m)")
    tipo: str = Field("Franklin", description="Tipo de dispositivo captor")

    class Config:
        populate_by_name = True


class MastilUpdateRequest(BaseModel):
    posicion_x: Optional[float] = Field(None)
    posicion_y: Optional[float] = Field(None)
    posicion_z: Optional[float] = Field(None)
    altura: Optional[float] = Field(None)
    tipo: Optional[str] = Field(None)

    class Config:
        populate_by_name = True


class MastilResponse(BaseModel):
    id: str
    id_modelo2d: Optional[str] = None
    id_proyecto: Optional[str] = None
    posicion_x: float
    posicion_y: float
    posicion_z: float
    altura: float
    tipo: str
    radio_cobertura: Optional[float] = None
    angulo_proteccion: Optional[float] = None
    fecha_creacion: Optional[datetime] = None


class CoberturaPunto(BaseModel):
    x: float
    y: float
    z: float
    protegido: bool
    distancia_minima_mastil: float
    mastil_cobertura_id: Optional[str] = None


class CoberturaResponse(BaseModel):
    id_proyecto: str
    nivel_proteccion: Optional[str] = None
    radio_esfera_rodante_r: float
    total_mastiles: int
    mastiles: List[MastilResponse]
    puntos_cobertura: List[CoberturaPunto]
    puntos_desprotegidos: List[CoberturaPunto]
    porcentaje_cobertura: float
    advertencias: List[str] = Field(default_factory=list)
