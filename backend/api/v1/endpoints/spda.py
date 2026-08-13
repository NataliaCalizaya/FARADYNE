from fastapi import APIRouter, HTTPException
from uuid import UUID

router = APIRouter()

@router.get("/{project_id}")
async def get_spda(project_id: UUID):
    raise HTTPException(status_code=501, detail="Not Implemented")
