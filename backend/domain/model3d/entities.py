from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from domain.model2d.value_objects import Point

class MeshType(Enum):
    PRISM = "PRISM"
    COMPLEX = "COMPLEX"
    ROOF = "ROOF"

class Volume(BaseModel):
    id: UUID
    name: str
    mesh_data: Dict[str, Any]
    height: float
    base_polygon: List[Point]

class Modelo3D(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    model2d_id: UUID
    volumes: List[Volume] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
