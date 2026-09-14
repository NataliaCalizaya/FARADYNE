from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlanoBase(BaseModel):
    id_proyecto: str = Field(..., description="ID del proyecto asociado")


class PlanoCreateResponse(BaseModel):
    id: str
    id_proyecto: str
    nombre_archivo: str
    tipo_archivo: str
    ruta_archivo: str
    tamano_bytes: int
    metadatos: Dict[str, Any]
    fecha_creacion: datetime
    id_modelo2d: Optional[str] = None


class PlanoPreviewResponse(BaseModel):
    id: str
    id_proyecto: str
    nombre_archivo: str
    tipo_archivo: str
    ruta_archivo: Optional[str] = None
    bounding_box: Dict[str, Any] = Field(default_factory=dict)
    capas: List[Dict[str, Any]] = Field(default_factory=list)
    cotas_altura: List[Dict[str, Any]] = Field(default_factory=list)
    poligonos: List[Dict[str, Any]] = Field(default_factory=list)
    lineas: List[Dict[str, Any]] = Field(default_factory=list)

