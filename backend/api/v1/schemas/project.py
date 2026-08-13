from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID
from domain.project.entities import ProjectStatus

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    address: Optional[str] = None

class ProjectRead(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    address: Optional[str]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
