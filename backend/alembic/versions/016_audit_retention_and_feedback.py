"""Add feedback comment storage and audit retention index.

Revision ID: 016
Revises: 015
Create Date: 2026-10-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rag_audit_logs", sa.Column("feedback_comment", sa.String(length=2000), nullable=True))
    op.create_index("ix_rag_audit_logs_created_at", "rag_audit_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rag_audit_logs_created_at", table_name="rag_audit_logs")
    op.drop_column("rag_audit_logs", "feedback_comment")
