from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Modelo3DCreateRequest(BaseModel):
    id_modelo2d: str = Field(..., alias="idModelo2D", description="ID del modelo 2D fuente")

    class Config:
        populate_by_name = True


class Modelo3DResponse(BaseModel):
    id: str
    id_modelo2d: str
    id_proyecto: str
    geometria_volumetrica: Dict[str, Any]
    vista_defecto: Dict[str, Any]
    fecha_creacion: datetime


class ResetViewRequest(BaseModel):
    camera: Optional[List[float]] = Field(default=None, example=[50.0, 50.0, 50.0])
    target: Optional[List[float]] = Field(default=None, example=[0.0, 0.0, 0.0])


class ResetViewResponse(BaseModel):
    id: str
    vista_defecto: Dict[str, Any]
    mensaje: str = "Vista restablecida a su posición por defecto"
