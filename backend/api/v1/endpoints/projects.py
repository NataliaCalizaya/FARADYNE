from fastapi import APIRouter, Depends
from uuid import UUID

router = APIRouter()

@router.get("/")
async def list_projects():
    return []

@router.post("/")
async def create_project():
    pass

@router.get("/{id}")
async def get_project(id: UUID):
    pass

@router.put("/{id}")
async def update_project(id: UUID):
    pass

@router.delete("/{id}")
async def delete_project(id: UUID):
    pass
