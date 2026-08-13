from typing import List
from domain.project.entities import Project

class ListProjectsUseCase:
    def execute(self, skip: int = 0, limit: int = 20) -> List[Project]:
        pass
