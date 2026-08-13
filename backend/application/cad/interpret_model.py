from uuid import UUID
from infrastructure.cad.raw_model.raw_cad_data import RawCADData
from domain.model2d.model import Modelo2D

class InterpretCADModelUseCase:
    def execute(self, raw_data: RawCADData, project_id: UUID) -> Modelo2D:
        pass
