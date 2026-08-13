from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    status: str
    model2d_id: Optional[UUID] = None
    message: str
