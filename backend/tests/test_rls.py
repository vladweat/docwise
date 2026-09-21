"""Postgres RLS hides other tenants' corpus rows when session org is not set."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.rls import bind_session_rls
from app.models.document import Document, DocumentStatus
from helpers import make_org, wipe_app_tables


@pytest.fixture
def clean_tables():
    db: Session = SessionLocal()
    wipe_app_tables(db)
    db.close()
    yield
    db = SessionLocal()
    wipe_app_tables(db)
    db.close()


def test_rls_hides_foreign_org_documents(clean_tables, monkeypatch):
    monkeypatch.delenv("RLS_TEST_FIXTURE_BYPASS", raising=False)

    seed = SessionLocal()
    try:
        bind_session_rls(seed, bypass=True)
        acme = make_org(seed, "Acme RLS")
        globex = make_org(seed, "Globex RLS")
        seed.add(
            Document(
                organization_id=acme.id,
                title="Acme secret",
                file_path=f"orgs/{acme.id}/a.pdf",
                file_hash=uuid4().hex,
                file_size_bytes=10,
                total_pages=1,
                access_roles=["all"],
                status=DocumentStatus.ready.value,
            )
        )
        seed.add(
            Document(
                organization_id=globex.id,
                title="Globex secret",
                file_path=f"orgs/{globex.id}/g.pdf",
                file_hash=uuid4().hex,
                file_size_bytes=10,
                total_pages=1,
                access_roles=["all"],
                status=DocumentStatus.ready.value,
            )
        )
        seed.commit()
    finally:
        seed.close()

    bare = SessionLocal()
    try:
        assert bare.query(Document).count() == 0
    finally:
        bare.close()

    scoped = SessionLocal()
    try:
        bind_session_rls(scoped, organization_id=acme.id)
        titles = {row.title for row in scoped.query(Document).all()}
        assert titles == {"Acme secret"}
    finally:
        scoped.close()
