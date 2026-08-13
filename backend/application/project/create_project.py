from schemas.project import ProjectCreate
from domain.project.entities import Project

class CreateProjectUseCase:
    def execute(self, data: ProjectCreate) -> Project:
        pass
