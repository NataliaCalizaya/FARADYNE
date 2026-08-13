from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, List
from uuid import UUID

class SemanticLayerType(Enum):
    WALLS = "WALLS"
    ROOF = "ROOF"
    FURNITURE = "FURNITURE"
    TEXT = "TEXT"
    DIMENSIONS = "DIMENSIONS"
    UNKNOWN = "UNKNOWN"

class EntityType(Enum):
    LINE = "LINE"
    POLYLINE = "POLYLINE"
    ARC = "ARC"
    CIRCLE = "CIRCLE"
    SPLINE = "SPLINE"
    TEXT = "TEXT"
    MTEXT = "MTEXT"
    INSERT = "INSERT"
    HATCH = "HATCH"

class Layer(BaseModel):
    id: str
    name: str
    color: str = "#FFFFFF"
    visible: bool = True
    locked: bool = False
    semantic_type: SemanticLayerType = SemanticLayerType.UNKNOWN

from .value_objects import Point

class Entity(BaseModel):
    id: UUID
    layer_id: str
    entity_type: EntityType
    geometry: dict
    attributes: dict = Field(default_factory=dict)

class Wall(BaseModel):
    id: UUID
    layer_id: str
    polyline: List[Point]
    thickness: Optional[float] = None

class Room(BaseModel):
    id: UUID
    name: Optional[str]
    polygon: List[Point]
    area: float = 0.0

class OpeningType(Enum):
    DOOR = "DOOR"
    WINDOW = "WINDOW"

class Opening(BaseModel):
    id: UUID
    opening_type: OpeningType
    position: Point
    width: float = 0.0

class RoofType(Enum):
    FLAT = "FLAT"
    PITCHED = "PITCHED"
    COMPLEX = "COMPLEX"

class Roof(BaseModel):
    polygon: List[Point]
    height: float
    roof_type: RoofType = RoofType.FLAT

class FloorHeight(BaseModel):
    floor_level: int
    floor_height: float
    ceiling_height: float
