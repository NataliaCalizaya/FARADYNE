from database.base import BaseModel
from sqlalchemy import Column, String, Integer, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

class Model2DRecord(BaseModel):
    __tablename__ = "model2d_records"
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    source = Column(String)
    source_filename = Column(String)
    model_data = Column(JSON)
