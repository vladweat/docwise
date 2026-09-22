"""Auth request/response schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    organization_name: str | None = Field(default=None, max_length=200)
    invite_token: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_org_or_invite(self) -> "RegisterRequest":
        token = (self.invite_token or "").strip()
        name = (self.organization_name or "").strip()
        if token:
            self.invite_token = token
            return self
        if not name:
            raise ValueError("organization_name is required")
        self.organization_name = name
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    id_token: str
    organization_name: str | None = Field(default=None, max_length=200)
    invite_token: str | None = Field(default=None, max_length=128)


class SwitchOrganizationRequest(BaseModel):
    organization_id: UUID
