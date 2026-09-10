"""Organization plan, billing_status, and quota period (M6a).

Revision ID: 008
Revises: 007
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("plan", sa.String(length=20), server_default="starter", nullable=False),
    )
    op.add_column(
        "organizations",
        sa.Column("billing_status", sa.String(length=20), server_default="active", nullable=False),
    )
    op.add_column("organizations", sa.Column("current_period_start", sa.DateTime(), nullable=True))
    op.add_column("organizations", sa.Column("current_period_end", sa.DateTime(), nullable=True))
    op.create_check_constraint(
        "ck_organizations_plan",
        "organizations",
        "plan IN ('starter', 'team', 'enterprise')",
    )
    op.create_check_constraint(
        "ck_organizations_billing_status",
        "organizations",
        "billing_status IN ('active', 'past_due', 'canceled')",
    )
    op.execute(
        sa.text(
            "UPDATE organizations SET current_period_start = now(), "
            "current_period_end = now() + interval '30 days' "
            "WHERE current_period_start IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_constraint("ck_organizations_billing_status", "organizations", type_="check")
    op.drop_constraint("ck_organizations_plan", "organizations", type_="check")
    op.drop_column("organizations", "current_period_end")
    op.drop_column("organizations", "current_period_start")
    op.drop_column("organizations", "billing_status")
    op.drop_column("organizations", "plan")
