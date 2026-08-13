from pydantic import BaseModel
from domain.model2d.model import Modelo2D

class Model2DRead(BaseModel):
    model: Modelo2D
