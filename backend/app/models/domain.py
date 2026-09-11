from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class DomainKind(str, enum.Enum):
    platform = "platform"
    custom = "custom"


class OrganizationDomain(Base):
    __tablename__ = "organization_domains"
    __table_args__ = (
        UniqueConstraint("hostname", name="uq_organization_domains_hostname"),
        CheckConstraint("kind IN ('platform', 'custom')", name="ck_organization_domains_kind"),
        Index("ix_organization_domains_organization_id", "organization_id"),
        Index(
            "uq_organization_domains_one_custom",
            "organization_id",
            unique=True,
            postgresql_where=text("kind = 'custom'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    hostname: Mapped[str] = mapped_column(String(253), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="domains")
