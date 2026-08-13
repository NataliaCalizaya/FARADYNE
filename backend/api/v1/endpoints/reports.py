from fastapi import APIRouter, HTTPException
from uuid import UUID

router = APIRouter()

@router.post("/{project_id}")
async def generate_report(project_id: UUID):
    raise HTTPException(status_code=501, detail="Not Implemented")
