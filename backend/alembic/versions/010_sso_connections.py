"""SSO connectors and organizations.sso_enforced (M6c).

Revision ID: 010
Revises: 009
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("sso_enforced", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_table(
        "organization_sso_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("protocol", sa.String(length=20), nullable=False, server_default="saml"),
        sa.Column("idp_entity_id", sa.String(length=512), nullable=True),
        sa.Column("idp_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attribute_map", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("jit_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("protocol IN ('saml', 'oidc')", name="ck_organization_sso_connections_protocol"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", name="uq_organization_sso_connections_org"),
    )


def downgrade() -> None:
    op.drop_table("organization_sso_connections")
    op.drop_column("organizations", "sso_enforced")
