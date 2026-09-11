"""Composite FK so chunk organization_id cannot drift from the parent document.

Revision ID: 013
Revises: 012
Create Date: 2026-09-10
"""

from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_documents_id_organization_id",
        "documents",
        ["id", "organization_id"],
    )
    op.create_foreign_key(
        "fk_document_chunks_document_organization",
        "document_chunks",
        "documents",
        ["document_id", "organization_id"],
        ["id", "organization_id"],
        ondelete="CASCADE",
    )
    # Composite FK supersedes document_id → documents.id; two paths break SQLAlchemy joins.
    op.drop_constraint("document_chunks_document_id_fkey", "document_chunks", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        "document_chunks_document_id_fkey",
        "document_chunks",
        "documents",
        ["document_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "fk_document_chunks_document_organization",
        "document_chunks",
        type_="foreignkey",
    )
    op.drop_constraint("uq_documents_id_organization_id", "documents", type_="unique")
