from typing import List, Optional

from pydantic import BaseModel


class MaterialItem(BaseModel):
    codigo: Optional[str] = None
    descripcion: str
    cantidad: int
    unidad: str = "un"


class ListadoMaterialesResponse(BaseModel):
    id_proyecto: str
    total_mastiles: int
    items: List[MaterialItem]