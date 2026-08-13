from domain.model2d.value_objects import Point, BoundingBox
from typing import List

class CoordinateTransformer:
    def transform(self, points: List[Point], translation, scale, rotation) -> List[Point]:
        pass

    def calculate_bounding_box(self, points: List[Point]) -> BoundingBox:
        pass

    def center_to_origin(self, points: List[Point]) -> List[Point]:
        pass
