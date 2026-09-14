from dataclasses import dataclass
from typing import Optional


@dataclass
class Mastil:
    id_mastil: Optional[int] = None
    coordenada_x: float = 0.0
    coordenada_y: float = 0.0
    altura: float = 0.0
    tipo: str = "Franklin"
    id_modelo3d: Optional[int] = None

