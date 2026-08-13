from domain.model2d.repository import IModel2DRepository
from domain.model2d.model import Modelo2D
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional

class Model2DRepository(IModel2DRepository):
    def __init__(self, db: Session):
        self.db = db

    def save(self, model: Modelo2D) -> Modelo2D:
        pass

    def get_by_id(self, model_id: UUID) -> Optional[Modelo2D]:
        pass

    def get_by_project_id(self, project_id: UUID) -> Optional[Modelo2D]:
        pass

    def delete(self, model_id: UUID) -> bool:
        pass
