from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    file_size_bytes: int
    total_pages: int | None = None
    access_roles: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentStatusResponse(BaseModel):
    id: UUID
    status: str
    last_error: str | None = None

    model_config = {"from_attributes": True}
