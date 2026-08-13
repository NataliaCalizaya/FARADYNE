from fastapi import APIRouter
from uuid import UUID

router = APIRouter()

@router.get("/{project_id}")
async def get_model3d(project_id: UUID):
    pass

@router.post("/{project_id}/generate")
async def generate_model3d(project_id: UUID):
    pass
