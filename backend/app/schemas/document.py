from datetime import datetime
from uuid import UUID

from typing import Literal

from pydantic import BaseModel, Field


class DocumentResponse(BaseModel):
    id: UUID
    title: str
    content_format: Literal["pdf", "docx"] = "pdf"
    file_size_bytes: int
    total_pages: int | None = None
    access_roles: list[str] = Field(default_factory=list)
    status: str
    last_error: str | None = None
    preview_snippet: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentAccessUpdate(BaseModel):
    access_roles: list[str] = Field(min_length=1)


class DocumentStatusResponse(BaseModel):
    id: UUID
    status: str
    last_error: str | None = None
    stage: str | None = Field(default=None, validation_alias="ingestion_stage")

    model_config = {"from_attributes": True, "populate_by_name": True}
