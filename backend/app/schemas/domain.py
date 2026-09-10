from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DomainUpsertRequest(BaseModel):
    """Custom hostname for this org. `organization_id` in extras is ignored as a tenant source."""

    model_config = ConfigDict(extra="allow")

    hostname: str | None = Field(default=None, max_length=253)


class DomainVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    token: str | None = Field(default=None, max_length=128)


class OrganizationDomainResponse(BaseModel):
    slug: str
    platform_hostnames: list[str]
    custom_hostname: str | None
    custom_verified: bool
    verified_at: datetime | None
    verification_token: str | None
    entitlement: bool
