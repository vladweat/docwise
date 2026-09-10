"""organization_domains for platform hosts and verified custom CNAMEs (M6d).

Revision ID: 011
Revises: 010
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PLATFORM_SUFFIXES = ("localhost", "docwise.app")


def upgrade() -> None:
    op.create_table(
        "organization_domains",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hostname", sa.String(length=253), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("verification_token", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('platform', 'custom')", name="ck_organization_domains_kind"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hostname", name="uq_organization_domains_hostname"),
    )
    op.create_index("ix_organization_domains_organization_id", "organization_domains", ["organization_id"])
    op.create_index(
        "uq_organization_domains_one_custom",
        "organization_domains",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'custom'"),
    )

    bind = op.get_bind()
    orgs = bind.execute(sa.text("SELECT id, slug FROM organizations"))
    insert = sa.text(
        "INSERT INTO organization_domains (organization_id, hostname, kind, verified_at) "
        "VALUES (:organization_id, :hostname, 'platform', now())"
    )
    for org_id, slug in orgs:
        for suffix in _PLATFORM_SUFFIXES:
            bind.execute(insert, {"organization_id": org_id, "hostname": f"{slug}.{suffix}"})


def downgrade() -> None:
    op.drop_index("uq_organization_domains_one_custom", table_name="organization_domains")
    op.drop_index("ix_organization_domains_organization_id", table_name="organization_domains")
    op.drop_table("organization_domains")
