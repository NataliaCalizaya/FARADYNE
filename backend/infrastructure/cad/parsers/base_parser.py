from abc import ABC, abstractmethod
from infrastructure.cad.interpreter.raw_cad_data import RawCADData

class BaseCADParser(ABC):
    @property
    @abstractmethod
    def format_name(self) -> str:
        pass

    @abstractmethod
    def parse(self, file_path: str) -> RawCADData:
        pass

    @abstractmethod
    def supports_format(self, extension: str) -> bool:
        pass
