from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MastilCreateRequest(BaseModel):
    id_modelo3d: str = Field(..., alias="idModelo3D", description="ID del modelo 3D")
    id_proyecto: Optional[str] = Field(None, alias="idProyecto", description="ID del proyecto")
    posicion_x: float = Field(..., alias="x", description="Coordenada X")
    posicion_y: float = Field(..., alias="y", description="Coordenada Y")
    posicion_z: float = Field(..., alias="z", description="Coordenada Z de la base del mástil")
    altura: float = Field(..., alias="altura", description="Altura h del mástil (m)")
    tipo: str = Field("Franklin", description="Tipo de dispositivo captor")

    class Config:
        populate_by_name = True


class MastilUpdateRequest(BaseModel):
    posicion_x: Optional[float] = Field(None, alias="x")
    posicion_y: Optional[float] = Field(None, alias="y")
    posicion_z: Optional[float] = Field(None, alias="z")
    altura: Optional[float] = Field(None)
    tipo: Optional[str] = Field(None)

    class Config:
        populate_by_name = True


class MastilResponse(BaseModel):
    id: str
    id_modelo3d: str
    id_proyecto: str
    posicion_x: float
    posicion_y: float
    posicion_z: float
    altura: float
    tipo: str
    radio_cobertura: Optional[float] = None
    angulo_proteccion: Optional[float] = None
    fecha_creacion: datetime


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
    total_mastiIes: int
    mastiIes: List[MastilResponse]
    puntos_cobertura: List[CoberturaPunto]
    puntos_desprotegidos: List[CoberturaPunto]
    porcentaje_cobertura: float
    advertencias: List[str] = Field(default_factory=list)
