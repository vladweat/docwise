from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel):
    doc_id: UUID
    doc_title: str
    page: int
    snippet: str


class ChatStreamRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    session_id: UUID | None = None

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class ChatFeedbackRequest(BaseModel):
    message_id: UUID
    rating: Literal[1, -1]
    comment: str | None = Field(default=None, max_length=2000)


class ChatMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    sources: list[Citation] = Field(default_factory=list)
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionSummary(BaseModel):
    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionSummary]
    total: int
    limit: int
    offset: int


class ChatSessionDetail(ChatSessionSummary):
    messages: list[ChatMessageOut] = Field(default_factory=list)
