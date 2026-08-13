from abc import ABC, abstractmethod
from infrastructure.cad.raw_model.raw_cad_data import RawCADData
from domain.model2d.model import Modelo2D

class BaseCADInterpreter(ABC):
    @abstractmethod
    def interpret(self, raw_data: RawCADData) -> Modelo2D:
        pass
