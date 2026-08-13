from uuid import UUID
from typing import Optional
from domain.project.entities import Project

class GetProjectUseCase:
    def execute(self, project_id: UUID) -> Optional[Project]:
        pass
