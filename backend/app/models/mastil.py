from dataclasses import dataclass
from typing import Optional


@dataclass
class Mastil:
    id_mastil: Optional[int] = None
    posicion_x: float = 0.0
    posicion_y: float = 0.0
    posicion_z: float = 0.0
    altura: float = 0.0
    tipo: str = "Franklin"
    id_modelo2d: Optional[int] = None

