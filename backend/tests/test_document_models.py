from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id
from helpers import make_org, wipe_app_tables

APP_DIR = Path(__file__).resolve().parents[1] / "app"
MAIN_PY = APP_DIR / "main.py"
LIFESPAN_PY = APP_DIR / "core" / "lifespan.py"
MIGRATIONS_PY = APP_DIR / "core" / "migrations.py"


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


def test_startup_uses_alembic_not_create_all():
    main_src = MAIN_PY.read_text()
    lifespan_src = LIFESPAN_PY.read_text()
    migrations_src = MIGRATIONS_PY.read_text()
    for source in (main_src, lifespan_src, migrations_src):
        assert "create_all" not in source
    assert "run_migrations" in lifespan_src
    assert "command.upgrade" in migrations_src


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
