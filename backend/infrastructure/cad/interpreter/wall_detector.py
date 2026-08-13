from typing import List
from domain.model2d.entities import Wall

class WallDetector:
    def detect(self, entities, layer_type_map) -> List[Wall]:
        raise NotImplementedError('Wall detection will be implemented in a future iteration')
