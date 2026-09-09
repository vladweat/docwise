from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    departments: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
