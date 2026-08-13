from database.base import BaseModel
from sqlalchemy import Column, String, Enum
import enum

class ProjectStatus(enum.Enum):
    DRAFT = "DRAFT"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"

class Project(BaseModel):
    __tablename__ = "projects"
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    address = Column(String, nullable=True)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)
