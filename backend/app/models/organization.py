from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.billing import BillingStatus as _BillingStatus

if TYPE_CHECKING:
    from app.models.domain import OrganizationDomain
    from app.models.sso import OrganizationSsoConnection
    from app.models.user import User


class OrganizationStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"


class OrganizationPlan(str, enum.Enum):
    starter = "starter"
    team = "team"
    enterprise = "enterprise"


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'suspended')", name="ck_organizations_status"),
        CheckConstraint(
            "plan IN ('starter', 'team', 'enterprise')",
            name="ck_organizations_plan",
        ),
        CheckConstraint(
            "billing_status IN ('active', 'past_due', 'canceled')",
            name="ck_organizations_billing_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrganizationStatus.active.value,
        server_default=OrganizationStatus.active.value,
    )
    plan: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrganizationPlan.starter.value,
        server_default=OrganizationPlan.starter.value,
    )
    billing_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=_BillingStatus.active.value,
        server_default=_BillingStatus.active.value,
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sso_enforced: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    llm_index_generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    sso_connection: Mapped["OrganizationSsoConnection | None"] = relationship(
        back_populates="organization",
        uselist=False,
        cascade="all, delete-orphan",
    )
    domains: Mapped[list["OrganizationDomain"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),
        CheckConstraint(
            "role IN ('admin', 'manager', 'employee')",
            name="ck_organization_memberships_role",
        ),
        Index("ix_organization_memberships_user_id", "user_id"),
        Index("ix_organization_memberships_organization_id", "organization_id"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    departments: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")

    def allowed_roles(self) -> list[str]:
        roles = {self.role, "all"}
        roles.update(self.departments or [])
        return sorted(roles)


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"
    __table_args__ = (
        CheckConstraint(
            "role IN ('admin', 'manager', 'employee')",
            name="ck_organization_invites_role",
        ),
        Index("ix_organization_invites_token_hash", "token_hash", unique=True),
        Index(
            "uq_organization_invites_pending_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    departments: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    invited_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    organization: Mapped[Organization] = relationship()


from app.models.domain import OrganizationDomain as _OrganizationDomain  # noqa: E402, F401
from app.models.sso import OrganizationSsoConnection as _OrganizationSsoConnection  # noqa: E402, F401
