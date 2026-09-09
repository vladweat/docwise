from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id

MAIN_PY = Path(__file__).resolve().parents[1] / "app" / "main.py"


@pytest.fixture
def db():
    session: Session = SessionLocal()
    session.query(DocumentChunk).delete()
    session.query(Document).delete()
    session.commit()
    yield session
    session.query(DocumentChunk).delete()
    session.query(Document).delete()
    session.commit()
    session.close()


def _document(**overrides) -> Document:
    payload = {
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
    source = MAIN_PY.read_text()
    assert "create_all" not in source
    assert "command.upgrade" in source


def test_document_and_chunk_roundtrip(db: Session):
    doc = _document(total_pages=2)
    db.add(doc)
    db.flush()

    chunk = DocumentChunk(
        document_id=doc.id,
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
    assert saved.page_number == 1
    assert saved.is_table is True
    assert saved.access_roles == stored.access_roles
    assert saved.embedding is not None
    assert len(saved.embedding) == 384
    assert saved.bbox["x0"] == 1
    assert saved.highlight_rects[0]["y1"] == 4
    assert saved.chunk_id == f"{doc.id}:1:0"


def test_file_hash_is_unique(db: Session):
    digest = "a" * 64
    db.add(_document(file_hash=digest, file_path="a/one.pdf"))
    db.commit()
    db.add(_document(file_hash=digest, file_path="a/two.pdf"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_invalid_status_rejected(db: Session):
    db.add(_document(status="indexing"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_delete_document_cascades_chunks(db: Session):
    doc = _document()
    db.add(doc)
    db.flush()
    db.add(
        DocumentChunk(
            document_id=doc.id,
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

    assert "ix_documents_file_hash" in by_name
    assert "unique" in by_name["ix_documents_file_hash"]
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
