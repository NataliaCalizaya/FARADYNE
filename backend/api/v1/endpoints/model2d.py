from fastapi import APIRouter
from uuid import UUID

router = APIRouter()

@router.get("/{project_id}")
async def get_model2d(project_id: UUID):
    pass
