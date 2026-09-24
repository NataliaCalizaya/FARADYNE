from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, Any, Optional


@dataclass
class Modelo3D:
    id_modelo3d: Optional[int] = None
    geometria_volumetrica: Dict[str, Any] = field(default_factory=dict)
    escala: Optional[float] = 1.0
    creado_en: Optional[date] = None
    altura_h: Optional[float] = 0.0
    id_modelo2d: Optional[int] = None
    vista_defecto: Optional[Dict[str, Any]] = None  # Para que coincida con la DB y el SQL
    actualizado_en: Optional[datetime] = None

