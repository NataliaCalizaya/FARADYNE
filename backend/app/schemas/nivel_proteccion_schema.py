from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel, Field


class NivelProteccionCalcularRequest(BaseModel):
    """HU04: payload de /niveles-proteccion/calcular (previsualización, no persiste)."""

    id_proyecto: str = Field(..., alias="idProyecto", description="ID del proyecto")
    id_zona: Optional[str] = Field(None, alias="idZona", description="ID de la zona ceraúnica (opcional)")
    departamento: Optional[str] = Field(None, description="Nombre del departamento si idZona no se provee")

    # Factores ambientales y constructivos IEC 62305 / IRAM 2184
    factor_a: float = Field(1.0, description="Tabla E.1 - Tipo de ocupación")
    factor_b: float = Field(1.0, description="Tabla E.2 - Tipo de construcción")
    factor_c: float = Field(1.0, description="Tabla E.3 - Contenido de la estructura")
    factor_d: float = Field(1.0, description="Tabla E.4 - Localización de la estructura")
    factor_e: float = Field(1.0, description="Tabla E.5 - Topografía")

    class Config:
        # El frontend manda snake_case (id_proyecto, id_zona, nivel_seleccionado),
        # no los alias en camelCase declarados arriba; se acepta cualquiera de
        # las dos formas para no romper los llamados existentes del cliente.
        populate_by_name = True


class NivelProteccionCreateRequest(NivelProteccionCalcularRequest):
    """HU04: payload de POST /niveles-proteccion (calcula y persiste).

    Nota: L/W/H ya NO se reciben acá. Se toman de lo persistido para el
    proyecto o, si es la primera vez, del Modelo3D (ver
    NivelProteccionRepository.get_dimensiones_by_proyecto_id).
    """

    nivel_seleccionado: Optional[str] = Field(
        None,
        alias="nivelSeleccionado",
        description="Nivel elegido libremente por el usuario en la grilla (I+, I, II, III, IV); si se omite se guarda el recomendado",
    )


class NivelProteccionResponse(BaseModel):
    id_nivel_proteccion: str
    id_proyecto: str
    id_zona: Optional[str] = None
    longitud_edificacion: float
    anchura_edificacion: float
    altura_edificacion: float
    margen_lateral: float
    formula_area_utilizada: str
    area_equivalente_ae: float
    frecuencia_impactos_nd: float
    frecuencia_tolerable_nc: float
    requiere_spcr: bool
    nivel_proteccion_recomendado: str
    nivel_proteccion_seleccionado: str
    eficiencia_proteccion: Optional[float] = None
    radio_esfera_rodante_r: float

    factores_riesgo: Dict[str, float] = {}

    fecha_calculo: datetime

    class Config:
        from_attributes = True