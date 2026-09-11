"""Independent FTS (tsvector+GIN) and org LLM-cache generation.

Revision ID: 012
Revises: 011
Create Date: 2026-09-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("llm_index_generation", sa.Integer(), server_default="0", nullable=False),
    )
    op.execute(
        sa.text(
            "ALTER TABLE document_chunks ADD COLUMN search_vector tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, coalesce(content, ''))) STORED"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX ix_document_chunks_search_vector "
            "ON document_chunks USING gin (search_vector)"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP INDEX IF EXISTS ix_document_chunks_search_vector"))
    op.execute(sa.text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS search_vector"))
    op.drop_column("organizations", "llm_index_generation")
