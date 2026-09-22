"""Members and invite API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.employee
    departments: list[str] = Field(default_factory=list)


class InviteCreateResponse(BaseModel):
    email: EmailStr
    role: str
    departments: list[str]
    status: str
    invite_token: str | None = None


class MemberResponse(BaseModel):
    user_id: UUID
    email: EmailStr
    role: str
    departments: list[str]
    created_at: datetime


class MemberListResponse(BaseModel):
    items: list[MemberResponse]
    total: int
