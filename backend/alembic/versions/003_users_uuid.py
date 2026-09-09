"""Convert integer user PKs to UUID (no-op if already UUID).

Revision ID: 003
Revises: 002
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    data_type = conn.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'id'"
        )
    ).scalar()
    if data_type in {"integer", "bigint"}:
        op.add_column("users", sa.Column("id_uuid", postgresql.UUID(as_uuid=True), nullable=True))
        op.execute(sa.text("UPDATE users SET id_uuid = gen_random_uuid()"))
        op.drop_constraint("users_pkey", "users", type_="primary")
        op.drop_column("users", "id")
        op.alter_column("users", "id_uuid", new_column_name="id", nullable=False)
        op.create_primary_key("users_pkey", "users", ["id"])
        op.execute(sa.text("ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid()"))

    op.execute(sa.text("ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role"))
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'manager', 'employee')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role", "users", type_="check")
