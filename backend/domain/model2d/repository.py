from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID
from .model import Modelo2D

class IModel2DRepository(ABC):
    @abstractmethod
    def save(self, model: Modelo2D) -> Modelo2D:
        pass

    @abstractmethod
    def get_by_id(self, model_id: UUID) -> Optional[Modelo2D]:
        pass

    @abstractmethod
    def get_by_project_id(self, project_id: UUID) -> Optional[Modelo2D]:
        pass

    @abstractmethod
    def delete(self, model_id: UUID) -> bool:
        pass
