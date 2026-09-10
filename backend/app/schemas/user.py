from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrganizationSummary(BaseModel):
    id: UUID
    name: str
    role: str
    departments: list[str] = Field(default_factory=list)


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    role: str
    departments: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    organization_id: UUID
    organization_name: str
    organizations: list[OrganizationSummary] = Field(default_factory=list)

    model_config = {"from_attributes": True}
