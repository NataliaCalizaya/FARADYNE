from database.base import BaseModel
from sqlalchemy import Column, String, JSON
from sqlalchemy.dialects.postgresql import UUID

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    entity_type = Column(String)
    entity_id = Column(UUID(as_uuid=True))
    action = Column(String)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    data = Column(JSON)
