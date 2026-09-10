"""Shared B2B SaaS tenancy: organizations, memberships, org_id on corpus rows.

Revision ID: 007
Revises: 006
Create Date: 2026-09-10
"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.CheckConstraint("status IN ('active', 'suspended')", name="ck_organizations_status"),
    )

    op.create_table(
        "organization_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("departments", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'manager', 'employee')",
            name="ck_organization_memberships_role",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),
    )
    op.create_index(
        "ix_organization_memberships_organization_id",
        "organization_memberships",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_organization_memberships_user_id",
        "organization_memberships",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "organization_invites",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("departments", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("invited_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('admin', 'manager', 'employee')",
            name="ck_organization_invites_role",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organization_invites_token_hash", "organization_invites", ["token_hash"], unique=True)
    op.create_index("ix_organization_invites_organization_id", "organization_invites", ["organization_id"], unique=False)
    op.create_index(
        "uq_organization_invites_pending_email",
        "organization_invites",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL"),
    )

    op.add_column("documents", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("document_chunks", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("chat_sessions", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("rag_audit_logs", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))

    conn = op.get_bind()
    needs_bootstrap = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM users) "
            "OR EXISTS (SELECT 1 FROM documents) "
            "OR EXISTS (SELECT 1 FROM chat_sessions) "
            "OR EXISTS (SELECT 1 FROM rag_audit_logs)"
        )
    ).scalar()
    if needs_bootstrap:
        org_id = uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, slug, status) "
                "VALUES (:id, :name, :slug, 'active')"
            ),
            {"id": org_id, "name": "Bootstrap", "slug": "bootstrap"},
        )
        conn.execute(
            sa.text(
                "INSERT INTO organization_memberships "
                "(id, organization_id, user_id, role, departments) "
                "SELECT gen_random_uuid(), :org_id, id, role, departments FROM users"
            ),
            {"org_id": org_id},
        )
        conn.execute(
            sa.text("UPDATE documents SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": org_id},
        )
        conn.execute(
            sa.text(
                "UPDATE document_chunks AS c SET organization_id = d.organization_id "
                "FROM documents AS d WHERE c.document_id = d.id AND c.organization_id IS NULL"
            ),
        )
        conn.execute(
            sa.text("UPDATE chat_sessions SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": org_id},
        )
        conn.execute(
            sa.text("UPDATE rag_audit_logs SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": org_id},
        )

    op.alter_column("documents", "organization_id", nullable=False)
    op.alter_column("document_chunks", "organization_id", nullable=False)
    op.alter_column("chat_sessions", "organization_id", nullable=False)
    op.alter_column("rag_audit_logs", "organization_id", nullable=False)

    op.create_foreign_key(
        "fk_documents_organization_id",
        "documents",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_document_chunks_organization_id",
        "document_chunks",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_chat_sessions_organization_id",
        "chat_sessions",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_rag_audit_logs_organization_id",
        "rag_audit_logs",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_documents_organization_id", "documents", ["organization_id"], unique=False)
    op.create_index("ix_document_chunks_organization_id", "document_chunks", ["organization_id"], unique=False)
    op.create_index("ix_chat_sessions_organization_id", "chat_sessions", ["organization_id"], unique=False)
    op.create_index("ix_rag_audit_logs_organization_id", "rag_audit_logs", ["organization_id"], unique=False)

    op.drop_index("ix_documents_file_hash", table_name="documents")
    op.create_index(
        "ix_documents_organization_id_file_hash",
        "documents",
        ["organization_id", "file_hash"],
        unique=True,
    )

    op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
    op.drop_column("users", "departments")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=20), server_default="employee", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("departments", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('admin', 'manager', 'employee')",
    )
    op.execute(
        sa.text(
            """
            UPDATE users AS u
            SET role = m.role, departments = m.departments
            FROM organization_memberships AS m
            WHERE m.user_id = u.id
              AND m.created_at = (
                  SELECT MIN(m2.created_at)
                  FROM organization_memberships AS m2
                  WHERE m2.user_id = u.id
              )
            """
        )
    )

    op.drop_index("ix_documents_organization_id_file_hash", table_name="documents")
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"], unique=True)

    op.drop_index("ix_rag_audit_logs_organization_id", table_name="rag_audit_logs")
    op.drop_index("ix_chat_sessions_organization_id", table_name="chat_sessions")
    op.drop_index("ix_document_chunks_organization_id", table_name="document_chunks")
    op.drop_index("ix_documents_organization_id", table_name="documents")
    op.drop_constraint("fk_rag_audit_logs_organization_id", "rag_audit_logs", type_="foreignkey")
    op.drop_constraint("fk_chat_sessions_organization_id", "chat_sessions", type_="foreignkey")
    op.drop_constraint("fk_document_chunks_organization_id", "document_chunks", type_="foreignkey")
    op.drop_constraint("fk_documents_organization_id", "documents", type_="foreignkey")
    op.drop_column("rag_audit_logs", "organization_id")
    op.drop_column("chat_sessions", "organization_id")
    op.drop_column("document_chunks", "organization_id")
    op.drop_column("documents", "organization_id")

    op.drop_index("uq_organization_invites_pending_email", table_name="organization_invites")
    op.drop_index("ix_organization_invites_organization_id", table_name="organization_invites")
    op.drop_index("ix_organization_invites_token_hash", table_name="organization_invites")
    op.drop_table("organization_invites")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_organization_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_table("organizations")
