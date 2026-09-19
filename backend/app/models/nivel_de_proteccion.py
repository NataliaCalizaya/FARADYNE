from dataclasses import dataclass
from typing import Optional


@dataclass
class NivelDeProteccion:
    id_nivel_proteccion: Optional[int] = None
    nivel: Optional[str] = None
    nd: float = 0.0
    nc: float = 0.0
    ae: float = 0.0
    eficiencia_minima: float = 0.0
    radio_esfera: float = 0.0
    factor_a_e: float = 0.0
    margen_lateral: float = 0.0
    id_proyecto: Optional[int] = None
    id_zona: Optional[int] = None

