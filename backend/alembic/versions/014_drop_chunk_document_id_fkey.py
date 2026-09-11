"""Drop redundant document_chunks.document_id FK if 013 already ran without that drop.

Revision ID: 014
Revises: 013
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS document_chunks_document_id_fkey"
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'document_chunks_document_id_fkey'
            ) THEN
                ALTER TABLE document_chunks
                    ADD CONSTRAINT document_chunks_document_id_fkey
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )
