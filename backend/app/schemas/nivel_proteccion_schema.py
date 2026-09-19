from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class NivelProteccionCreateRequest(BaseModel):
    id_proyecto: str = Field(..., alias="idProyecto", description="ID del proyecto")
    id_zona: Optional[str] = Field(None, alias="idZona", description="ID de la zona ceraúnica (opcional)")
    departamento: Optional[str] = Field(None, description="Nombre del departamento si idZona no se provee")
    longitud_edificacion: Optional[float] = Field(None, description="Longitud L (m), si se omite se toma del modelo 3D")
    anchura_edificacion: Optional[float] = Field(None, description="Anchura W (m), si se omite se toma del modelo 3D")
    altura_edificacion: Optional[float] = Field(None, description="Altura H (m), si se omite se toma del modelo 3D")

    # Factores ambientales y constructivos IEC 62305 / IRAM 2184
    factor_ubicacion_cd: float = Field(1.0, description="Factor de ubicación Cd (1.0 aislado, 0.5 rodeado)")
    factor_estructura_cb: float = Field(1.0, description="Factor de estructura Cb")
    factor_contenido_cc: float = Field(1.0, description="Factor de contenido Cc")
    factor_lineas_ce: float = Field(1.0, description="Factor de líneas de servicio Ce")

    class Config:
        populate_by_name = True


class NivelProteccionResponse(BaseModel):
    id: str
    id_proyecto: str
    id_zona: Optional[str] = None
    longitud_edificacion: float
    anchura_edificacion: float
    altura_edificacion: float
    area_equivalente_ae: float
    frecuencia_impactos_nd: float
    frecuencia_tolerable_nc: float
    requiere_spcr: bool
    nivel_proteccion_calculado: Optional[str] = None
    eficiencia_proteccion: Optional[float] = None
    factores_riesgo: Dict[str, Any]
    fecha_calculo: datetime
