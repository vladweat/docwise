"""RLS on corpus tables only (documents + chunks).

Revision ID: 015
Revises: 014
Create Date: 2026-09-21

Chat and audit rows are always scoped in application SQL (session org + user).
RLS here is for the RAG tables where a missing org filter on one query path
would leak another tenant's indexed text.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CORPUS_TABLES = ("documents", "document_chunks")

_FUNCTIONS = """
CREATE OR REPLACE FUNCTION docwise_rls_bypass() RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT coalesce(current_setting('app.rls_bypass', true), '') = 'on';
$$;

CREATE OR REPLACE FUNCTION docwise_current_organization_id() RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.organization_id', true), '')::uuid;
$$;

CREATE OR REPLACE FUNCTION docwise_tenant_visible(org_id uuid) RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT docwise_rls_bypass() OR docwise_current_organization_id() = org_id;
$$;
"""


def upgrade() -> None:
    op.execute(_FUNCTIONS)

    for table in _CORPUS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY docwise_{table}_tenant ON {table}
              FOR ALL
              USING (docwise_tenant_visible(organization_id))
              WITH CHECK (docwise_tenant_visible(organization_id))
            """
        )


def downgrade() -> None:
    for table in reversed(_CORPUS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS docwise_{table}_tenant ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS docwise_tenant_visible(uuid)")
    op.execute("DROP FUNCTION IF EXISTS docwise_current_organization_id()")
    op.execute("DROP FUNCTION IF EXISTS docwise_rls_bypass()")
