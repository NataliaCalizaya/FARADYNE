from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class MemoriaDescriptiva:
    id_memoria: Optional[int] = None
    ruta_pdf: Optional[str] = None
    declaracion_decreto_351_79: bool = False
    fecha_generacion: Optional[date] = None
    id_proyecto: Optional[int] = None

