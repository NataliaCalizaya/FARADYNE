from uuid import UUID
from infrastructure.cad.parsers.dxf.dxf_parser import DXFParser
from infrastructure.cad.raw_model.raw_cad_data import RawCADData

class ParseDXFUseCase:
    def __init__(self):
        self.parser = DXFParser()

    def execute(self, file_path: str, project_id: UUID) -> RawCADData:
        return self.parser.parse(file_path)
