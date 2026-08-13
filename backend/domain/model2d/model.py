from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from uuid import UUID, uuid4
from datetime import datetime
from .entities import Layer, Entity, Wall, Room, Opening, Roof, FloorHeight
from .value_objects import BoundingBox

class Modelo2D(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    source: Literal['dxf', 'dwg', 'pdf', 'image', 'manual']
    source_filename: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)
    bounding_box: Optional[BoundingBox] = None
    layers: List[Layer] = Field(default_factory=list)
    entities: List[Entity] = Field(default_factory=list)
    walls: List[Wall] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)
    openings: List[Opening] = Field(default_factory=list)
    roof: Optional[Roof] = None
    heights: List[FloorHeight] = Field(default_factory=list)

    def get_layer_by_id(self, layer_id: str) -> Optional[Layer]:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def get_entities_by_layer(self, layer_id: str) -> List[Entity]:
        return [entity for entity in self.entities if entity.layer_id == layer_id]

    def get_visible_layers(self) -> List[Layer]:
        return [layer for layer in self.layers if layer.visible]
