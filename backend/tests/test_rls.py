"""Postgres RLS on corpus tables."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.rls import bind_session_rls
from app.services.ingestion.worker import fetch_document_for_ingestion
from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM, make_chunk_id
from app.services.retrieval.types import chunk_acl_filter
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


def _no_fixture_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RLS_TEST_FIXTURE_BYPASS", raising=False)


def _vec(seed: int) -> list[float]:
    return [((seed + offset) % 17) / 17.0 for offset in range(EMBEDDING_DIM)]


def _seed_two_org_corpus(db: Session) -> tuple:
    bind_session_rls(db, bypass=True)
    acme = make_org(db, "Acme RLS")
    globex = make_org(db, "Globex RLS")
    acme_doc = Document(
        organization_id=acme.id,
        title="Acme handbook",
        file_path=f"orgs/{acme.id}/a.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=10,
        total_pages=1,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    globex_doc = Document(
        organization_id=globex.id,
        title="Globex handbook",
        file_path=f"orgs/{globex.id}/g.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=10,
        total_pages=1,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    db.add(acme_doc)
    db.add(globex_doc)
    db.flush()
    db.add(
        DocumentChunk(
            document_id=acme_doc.id,
            organization_id=acme.id,
            chunk_id=make_chunk_id(acme_doc.id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="acme-retrieval-marker",
            token_count=3,
            embedding=_vec(1),
            doc_title=acme_doc.title,
        )
    )
    db.add(
        DocumentChunk(
            document_id=globex_doc.id,
            organization_id=globex.id,
            chunk_id=make_chunk_id(globex_doc.id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="globex-retrieval-marker",
            token_count=3,
            embedding=_vec(2),
            doc_title=globex_doc.title,
        )
    )
    db.commit()
    return acme, globex, acme_doc, globex_doc


def _buggy_chunk_query_no_org_filter(db: Session, allowed_roles: list[str]):
    """Simulates a forgotten `organization_id` conjunct in retrieval SQL."""
    return (
        db.query(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(Document.status == DocumentStatus.ready.value)
        .filter(chunk_acl_filter(allowed_roles))
    )


def test_rls_hides_foreign_org_documents(clean_tables, monkeypatch):
    _no_fixture_bypass(monkeypatch)

    seed = SessionLocal()
    try:
        acme, globex, _, _ = _seed_two_org_corpus(seed)
        assert acme.id != globex.id
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
        assert titles == {"Acme handbook"}
    finally:
        scoped.close()


def test_rls_blocks_retrieval_query_missing_org_filter(clean_tables, monkeypatch):
    _no_fixture_bypass(monkeypatch)

    seed = SessionLocal()
    try:
        acme, globex, _, _ = _seed_two_org_corpus(seed)
    finally:
        seed.close()

    unscoped = SessionLocal()
    try:
        assert _buggy_chunk_query_no_org_filter(unscoped, ["employee", "all"]).count() == 0
    finally:
        unscoped.close()

    acme_db = SessionLocal()
    try:
        bind_session_rls(acme_db, organization_id=acme.id)
        rows = _buggy_chunk_query_no_org_filter(acme_db, ["employee", "all"]).all()
        assert len(rows) == 1
        assert "acme-retrieval-marker" in rows[0].content
        assert "globex-retrieval-marker" not in rows[0].content
    finally:
        acme_db.close()

    globex_db = SessionLocal()
    try:
        bind_session_rls(globex_db, organization_id=globex.id)
        rows = _buggy_chunk_query_no_org_filter(globex_db, ["employee", "all"]).all()
        assert len(rows) == 1
        assert "globex-retrieval-marker" in rows[0].content
    finally:
        globex_db.close()


def test_worker_document_lookup_scopes_rls(clean_tables, monkeypatch):
    _no_fixture_bypass(monkeypatch)

    seed = SessionLocal()
    try:
        acme, globex, acme_doc, globex_doc = _seed_two_org_corpus(seed)
    finally:
        seed.close()

    worker_db = SessionLocal()
    try:
        assert worker_db.get(Document, acme_doc.id) is None
        assert worker_db.get(Document, globex_doc.id) is None

        loaded = fetch_document_for_ingestion(worker_db, acme_doc.id)
        assert loaded is not None
        assert loaded.id == acme_doc.id

        visible = {row.id for row in worker_db.query(Document).all()}
        assert visible == {acme_doc.id}
        assert globex_doc.id not in visible
    finally:
        worker_db.close()
