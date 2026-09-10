from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.models.organization import Organization, OrganizationMembership
from app.models.user import User


@dataclass(frozen=True)
class Principal:
    """Authenticated caller in one organization. Role and departments come from membership."""

    user: User
    membership: OrganizationMembership
    organization: Organization

    @property
    def id(self) -> UUID:
        return self.user.id

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def is_active(self) -> bool:
        return bool(self.user.is_active)

    @property
    def created_at(self) -> datetime:
        return self.user.created_at

    @property
    def role(self) -> str:
        return self.membership.role

    @property
    def departments(self) -> list[str]:
        return list(self.membership.departments or [])

    @property
    def organization_id(self) -> UUID:
        return self.organization.id

    @property
    def organization_name(self) -> str:
        return self.organization.name

    def allowed_roles(self) -> list[str]:
        return self.membership.allowed_roles()
