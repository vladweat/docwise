from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.organization import Organization


class SsoProtocol(str, enum.Enum):
    saml = "saml"
    oidc = "oidc"


class OrganizationSsoConnection(Base):
    __tablename__ = "organization_sso_connections"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_organization_sso_connections_org"),
        CheckConstraint("protocol IN ('saml', 'oidc')", name="ck_organization_sso_connections_protocol"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    protocol: Mapped[str] = mapped_column(String(20), nullable=False, default=SsoProtocol.saml.value)
    idp_entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    idp_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    attribute_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    jit_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="sso_connection")
