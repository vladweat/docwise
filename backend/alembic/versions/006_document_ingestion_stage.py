"""Ingestion pipeline stage for status polling (parse → chunk → embed).

Revision ID: 006
Revises: 005
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ingestion_stage", sa.String(length=20), nullable=True))
    op.create_check_constraint(
        "ck_documents_ingestion_stage",
        "documents",
        "ingestion_stage IS NULL OR ingestion_stage IN ('parse', 'chunk', 'embed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_ingestion_stage", "documents", type_="check")
    op.drop_column("documents", "ingestion_stage")
