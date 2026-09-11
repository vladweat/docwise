from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.sso import SsoProtocol
from app.models.user import UserRole


class SsoAttributeRule(BaseModel):
    group: str = Field(min_length=1, max_length=128)
    role: UserRole | None = None
    departments: list[str] = Field(default_factory=list)

    @field_validator("group")
    @classmethod
    def normalize_group(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("group is required")
        return cleaned

    @field_validator("departments")
    @classmethod
    def normalize_departments(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            role = item.strip().lower()
            if not role or role in seen:
                continue
            seen.add(role)
            out.append(role)
        return out


class SsoAttributeMap(BaseModel):
    default_role: UserRole = UserRole.employee
    default_departments: list[str] = Field(default_factory=list)
    rules: list[SsoAttributeRule] = Field(default_factory=list)

    @field_validator("default_departments")
    @classmethod
    def normalize_default_departments(cls, value: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            role = item.strip().lower()
            if not role or role in seen:
                continue
            seen.add(role)
            out.append(role)
        return out


class SsoUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocol: SsoProtocol = SsoProtocol.saml
    idp_entity_id: str | None = Field(default=None, max_length=512)
    idp_metadata: dict = Field(default_factory=dict)
    jit_enabled: bool = False
    attribute_map: SsoAttributeMap = Field(default_factory=SsoAttributeMap)
    sso_enforced: bool = False


class SsoConnectionResponse(BaseModel):
    configured: bool
    slug: str
    protocol: str
    idp_entity_id: str | None
    idp_metadata: dict
    jit_enabled: bool
    attribute_map: dict
    sso_enforced: bool
    login_path: str
    acs_path: str
    provider: str


class DevSsoAssertion(BaseModel):
    """Compose fixture. `organization_id` / `org_id` in extras are ignored."""

    model_config = ConfigDict(extra="allow")

    email: EmailStr
    email_verified: bool = False
    groups: list[str] = Field(default_factory=list)
