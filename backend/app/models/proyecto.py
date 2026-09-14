from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Proyecto:
    id_proyecto: Optional[int] = None
    nombre: str = ""
    cliente: Optional[str] = None
    ubicacion: Optional[str] = None
    fecha_creacion: Optional[date] = None

