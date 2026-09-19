from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Any, Optional


@dataclass
class Modelo3D:
    id_modelo3d: Optional[int] = None
    geometria_volumetrica: Dict[str, Any] = field(default_factory=dict)
    escala: Optional[float] = 1.0
    fecha_generacion: Optional[date] = None
    altura_h: Optional[float] = 0.0
    id_modelo2d: Optional[int] = None

