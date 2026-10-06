from datetime import date
from typing import Optional

from pydantic import BaseModel


class MemoriaGenerateRequest(BaseModel):
    declaracion_decreto_351_79: bool = True


class MemoriaResponse(BaseModel):
    id_memoria: int
    id_proyecto: int
    ruta_pdf: Optional[str] = None
    declaracion_decreto_351_79: bool
    fecha_generacion: date
