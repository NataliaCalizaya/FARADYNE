from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class Plano:
    id_plano: Optional[int] = None
    nombre_archivo: str = ""
    tipo_archivo: str = ""
    ruta_archivo: str = ""
    fecha_carga: Optional[date] = None
    id_proyecto: Optional[int] = None
    

