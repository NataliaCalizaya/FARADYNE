from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class SuperficieEsfera(BaseModel):
    id: str
    mastiles_ids: List[str]
    puntas: List[List[float]]
    centro_esfera: List[float]
    radio: float
    radio_circunscrito: float
    altura_centro_sobre_plano: float
    forma: str
    vertices: List[List[float]]      # [x, y, z]
    triangulos: List[List[int]]      # índices a vertices

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
    motivo: str
    mensaje: str = ""
    area_m2: float
    centroide: Dict[str, float]
    poligono: List[List[float]]
    huecos: List[List[List[float]]] = []

# dentro de CoberturaResponse:
superficies_esfera: List[SuperficieEsfera] = []
triangulos_sin_esfera: List[TernaSinEsfera] = []
zonas_desprotegidas: List[ZonaDesprotegida] = []
# y en los items de puntos_*: superficie_id: Optional[str] = None, motivo: Optional[str] = None