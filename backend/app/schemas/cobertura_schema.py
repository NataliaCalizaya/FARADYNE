"""app.schemas.cobertura_schema

Contrato de la cobertura SPDA (HU05): esfera rodante por ternas de mástiles.
`CoberturaResponse` vive acá; el router de cobertura DEBE importarlo de este
módulo (si sigue importando el de mastil_schema, FastAPI descarta los campos
nuevos y el visor 3D no recibe superficies ni zonas).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.schemas.mastil_schema import MastilResponse


class SuperficieEsfera(BaseModel):
    id: str
    mastiles_ids: List[str]
    puntas: List[List[float]]
    centro_esfera: List[float]
    radio: float
    radio_circunscrito: float
    altura_centro_sobre_plano: float
    forma: str
    vertices: List[List[float]] = []   # [x, y, z]
    triangulos: List[List[int]] = []   # índices a `vertices`


class TernaSinEsfera(BaseModel):
    id: str
    mastiles_ids: List[str]
    puntas: List[List[float]]
    motivo: str
    mensaje: str
    radio_esfera: float
    radio_circunscrito: Optional[float] = None


class ZonaDesprotegida(BaseModel):
    id: str
    id_prisma: Optional[str] = None
    motivo: str
    mensaje: str = ""
    area_m2: float
    centroide: Dict[str, float]
    poligono: List[List[float]]
    huecos: List[List[List[float]]] = []


class PrismaCobertura(BaseModel):
    id: str
    area_m2: float
    area_protegida_m2: float
    porcentaje_cobertura: float
    estado: str  # "protegido" | "parcial" | "desprotegido"


class CoberturaResponse(BaseModel):
    id_proyecto: str
    nivel_proteccion: str
    radio_esfera_rodante_r: float
    total_mastiles: int
    mastiles: List[MastilResponse] = []

    superficies_esfera: List[SuperficieEsfera] = []
    triangulos_sin_esfera: List[TernaSinEsfera] = []
    zonas_desprotegidas: List[ZonaDesprotegida] = []
    prismas: List[PrismaCobertura] = []

    puntos_cobertura: List[Dict[str, Any]] = []
    puntos_desprotegidos: List[Dict[str, Any]] = []
    porcentaje_cobertura: float = 0.0
    advertencias: List[str] = []

    # Solo lo completa POST /cobertura/proyecto/{id}/guardar
    guardado: bool = False
    fecha_simulacion: Optional[datetime] = None