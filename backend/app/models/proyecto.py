from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class Proyecto:
    id_proyecto: Optional[int] = None
    nombre: str = ""
    cliente: Optional[str] = None
    descripcion: Optional[str] = None
    ubicacion: Optional[str] = None
    departamento: Optional[str] = None
    provincia: Optional[str] = None
    localidad: Optional[str] = None
    estado: str = "borrador"
    fecha_creacion: Optional[date] = None
    fecha_del_proyecto: Optional[date] = None

