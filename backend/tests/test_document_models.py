"""Document/chunk ORM constraints and ACL columns."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.lifespan import lifespan
from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id
from helpers import make_org, wipe_app_tables


@pytest.fixture
def db():
    session: Session = SessionLocal()
    wipe_app_tables(session)
    yield session
    wipe_app_tables(session)
    session.close()


def _document(org, **overrides) -> Document:
    payload = {
        "organization_id": org.id,
        "title": "Policy.pdf",
        "file_path": f"{uuid4()}/Policy.pdf",
        "file_hash": uuid4().hex,
        "file_size_bytes": 1024,
        "access_roles": ["hr", "admin"],
        "status": DocumentStatus.pending.value,
    }
    payload.update(overrides)
    return Document(**payload)


def test_api_lifespan_does_not_run_schema_migrations(monkeypatch):
    import app.core.lifespan as lifespan_module
    from app.main import app

    calls = []
    monkeypatch.setattr(lifespan_module, "assert_secret_key", lambda: None)
    monkeypatch.setattr(lifespan_module, "ensure_documents_bucket", lambda: None)
    monkeypatch.setattr(lifespan_module, "run_migrations", lambda: calls.append("migrate"), raising=False)

    async def start_api():
        async with lifespan(app):
            pass

    asyncio.run(start_api())

    assert calls == []


def test_migration_cli_bootstraps_runtime_role_before_alembic(monkeypatch):
    import app.core.migration_cli as migration_cli

    calls = []
    monkeypatch.setattr(migration_cli, "ensure_rls_runtime_role", lambda: calls.append("role"))
    monkeypatch.setattr(migration_cli, "run_migrations", lambda: calls.append("migrate"))

    migration_cli.main()

    assert calls == ["role", "migrate"]


def test_document_and_chunk_roundtrip(db: Session):
    org = make_org(db)
    doc = _document(org, total_pages=2)
    db.add(doc)
    db.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
        organization_id=doc.organization_id,
        chunk_id=make_chunk_id(doc.id, 1, 0),
        page_number=1,
        section_title="Expenses",
        is_table=True,
        access_roles=list(doc.access_roles),
        content="| Header | Amount |\n| --- | --- |\n| Taxi | 40 |",
        token_count=12,
        embedding=[0.0] * 384,
        doc_title=doc.title,
        bbox={"x0": 1, "y0": 2, "x1": 3, "y1": 4},
        highlight_rects=[{"x0": 1, "y0": 2, "x1": 3, "y1": 4}],
    )
    db.add(chunk)
    db.commit()

    stored = db.get(Document, doc.id)
    assert stored is not None
    assert stored.status == "pending"
    assert stored.access_roles == ["hr", "admin"]
    assert stored.last_error is None
    assert len(stored.chunks) == 1
    saved = stored.chunks[0]
    fts = db.execute(
        text("SELECT search_vector IS NOT NULL FROM document_chunks WHERE id = :id"),
        {"id": saved.id},
    ).scalar()
    assert fts is True
    assert saved.page_number == 1
    assert saved.is_table is True
    assert saved.access_roles == stored.access_roles
    assert saved.embedding is not None
    assert len(saved.embedding) == 384
    assert saved.bbox["x0"] == 1
    assert saved.highlight_rects[0]["y1"] == 4
    assert saved.chunk_id == f"{doc.id}:1:0"


def test_file_hash_is_unique_per_organization(db: Session):
    org = make_org(db)
    other = make_org(db)
    digest = "a" * 64
    db.add(_document(org, file_hash=digest, file_path="a/one.pdf"))
    db.commit()
    db.add(_document(org, file_hash=digest, file_path="a/two.pdf"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(_document(other, file_hash=digest, file_path="b/same.pdf"))
    db.commit()


def test_invalid_status_rejected(db: Session):
    org = make_org(db)
    db.add(_document(org, status="indexing"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_delete_document_cascades_chunks(db: Session):
    org = make_org(db)
    doc = _document(org)
    db.add(doc)
    db.flush()
    db.add(
        DocumentChunk(
            document_id=doc.id,
            organization_id=doc.organization_id,
            chunk_id=make_chunk_id(doc.id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="hello",
        )
    )
    db.commit()
    chunk_id = doc.chunks[0].id
    db.delete(doc)
    db.commit()
    assert db.get(Document, doc.id) is None
    assert db.get(DocumentChunk, chunk_id) is None


def test_required_indexes_exist(db: Session):
    rows = db.execute(
        text(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' AND tablename IN ('documents', 'document_chunks')"
        )
    ).mappings().all()
    by_name = {row["indexname"]: row["indexdef"].lower() for row in rows}

    assert "ix_documents_organization_id_file_hash" in by_name
    assert "unique" in by_name["ix_documents_organization_id_file_hash"]
    assert "ix_documents_organization_id" in by_name
    assert "ix_document_chunks_organization_id" in by_name
    assert "ix_documents_status" in by_name
    assert "ix_documents_access_roles" in by_name
    assert "gin" in by_name["ix_documents_access_roles"]
    assert "ix_document_chunks_access_roles" in by_name
    assert "gin" in by_name["ix_document_chunks_access_roles"]
    assert "ix_document_chunks_embedding_hnsw" in by_name
    embedding_def = by_name["ix_document_chunks_embedding_hnsw"]
    assert "hnsw" in embedding_def
    assert "vector_cosine_ops" in embedding_def
    assert "ix_document_chunks_chunk_id" in by_name
    assert "ix_document_chunks_search_vector" in by_name
    assert "gin" in by_name["ix_document_chunks_search_vector"]
    assert "search_vector" in by_name["ix_document_chunks_search_vector"]
    unique_names = db.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE contype = 'u' AND conrelid = 'documents'::regclass"
        )
    ).scalars().all()
    assert "uq_documents_id_organization_id" in unique_names
    fks = db.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE contype = 'f' AND conrelid = 'document_chunks'::regclass"
        )
    ).scalars().all()
    assert "fk_document_chunks_document_organization" in fks
    assert "document_chunks_document_id_fkey" not in fks


def test_chunk_organization_must_match_document(db: Session):
    org = make_org(db)
    other = make_org(db)
    doc = _document(org)
    db.add(doc)
    db.flush()
    db.add(
        DocumentChunk(
            document_id=doc.id,
            organization_id=other.id,
            chunk_id=make_chunk_id(doc.id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="drift",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
