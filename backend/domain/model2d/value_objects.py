from pydantic import BaseModel

class Point(BaseModel):
    x: float
    y: float
    z: float = 0.0

    class Config:
        frozen = True

class BoundingBox(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def area(self) -> float:
        return self.width * self.height

    class Config:
        frozen = True

class Height(BaseModel):
    value: float
    unit: str = 'm'

    class Config:
        frozen = True
