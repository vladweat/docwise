from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.celery_config import process_document_task
from app.core.database import SessionLocal
from app.models.document import EMBEDDING_DIM, Document, DocumentChunk, DocumentStatus, make_chunk_id
from app.services.embeddings import EmbeddingError
from app.services.ingestion import (
    IndexResult,
    IngestionError,
    index_pdf,
    persist_ingestion_failure,
    run_ingestion,
)
from app.services.storage import StorageError
from pdf_fixtures import blank_pdf_bytes, policy_pdf_bytes

MIN_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise StorageError("missing")
        return self.objects[key]

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


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


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture(autouse=True)
def stub_embeddings(monkeypatch):
    captured: dict[str, list[str]] = {"texts": []}

    def fake_embed_texts(texts, *, embedder=None):
        captured["texts"] = list(texts)
        return [
            [float((index + offset) % 7) for offset in range(EMBEDDING_DIM)]
            for index in range(len(texts))
        ]

    monkeypatch.setattr("app.services.ingestion.embed_texts", fake_embed_texts)
    return captured


@pytest.fixture(autouse=True)
def locks(monkeypatch):
    held: set[str] = set()

    def acquire(document_id, ttl=3600):
        key = str(document_id)
        if key in held:
            return False
        held.add(key)
        return True

    def release(document_id):
        held.discard(str(document_id))

    monkeypatch.setattr("app.services.ingestion.acquire_indexing_lock", acquire)
    monkeypatch.setattr("app.services.ingestion.release_indexing_lock", release)
    return held


def _seed(db: Session, storage: FakeStorage, *, pdf: bytes = MIN_PDF, chunks: int = 0) -> Document:
    document_id = uuid4()
    key = f"{document_id}/Policy.pdf"
    storage.objects[key] = pdf
    document = Document(
        id=document_id,
        title="Policy.pdf",
        file_path=key,
        file_hash=uuid4().hex + uuid4().hex[:32],
        file_size_bytes=len(pdf),
        access_roles=["hr", "admin"],
        status=DocumentStatus.pending.value,
    )
    db.add(document)
    db.flush()
    for ordinal in range(chunks):
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_id=make_chunk_id(document.id, 1, ordinal),
                page_number=1,
                access_roles=list(document.access_roles),
                content=f"old-{ordinal}",
                token_count=1,
            )
        )
    db.commit()
    db.refresh(document)
    return document


def _index_chunk(content: str, pages: int = 2):
    def _index(db: Session, document: Document, pdf_bytes: bytes) -> IndexResult:
        assert pdf_bytes.startswith(b"%PDF")
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_id=make_chunk_id(document.id, 1, 0),
                page_number=1,
                access_roles=list(document.access_roles),
                content=content,
                token_count=1,
                doc_title=document.title,
            )
        )
        return IndexResult(chunk_count=1, total_pages=pages)

    return _index


def test_task_name_is_process_document():
    assert process_document_task.name == "ingestion.process_document"


def test_process_document_task_delegates_to_run_ingestion(monkeypatch):
    closed: list[bool] = []

    class FakeSession:
        def close(self):
            closed.append(True)

        def rollback(self):
            pass

    monkeypatch.setattr("app.celery_config.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr(
        "app.celery_config.run_ingestion",
        lambda db, document_id: {"status": "ready", "document_id": document_id},
    )
    result = process_document_task.apply(args=["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]).get()
    assert result == {"status": "ready", "document_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}
    assert closed


def test_process_document_task_persists_failure_on_exception(monkeypatch):
    persisted: list[str] = []
    released: list[str] = []
    captured: list[str] = []

    class FakeSession:
        def close(self):
            pass

        def rollback(self):
            pass

    def boom(db, document_id):
        raise RuntimeError("worker boom")

    monkeypatch.setattr("app.celery_config.SessionLocal", lambda: FakeSession())
    monkeypatch.setattr("app.celery_config.run_ingestion", boom)
    monkeypatch.setattr(
        "app.celery_config.persist_ingestion_failure",
        lambda db, document_id, exc: persisted.append(str(document_id)),
    )
    monkeypatch.setattr(
        "app.celery_config.release_indexing_lock",
        lambda document_id: released.append(str(document_id)),
    )
    monkeypatch.setattr(
        "app.celery_config.capture_pipeline_error",
        lambda component, exc: captured.append(component),
    )

    with pytest.raises(RuntimeError, match="worker boom"):
        process_document_task.apply(args=["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]).get()

    assert persisted == ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]
    assert released == ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]
    assert captured == ["ingestion"]


def test_downloads_from_minio_and_marks_ready(db: Session, storage: FakeStorage, locks: set[str]):
    document = _seed(db, storage)
    seen: dict[str, bytes] = {}

    def index_fn(session: Session, doc: Document, pdf_bytes: bytes) -> IndexResult:
        seen["bytes"] = pdf_bytes
        return _index_chunk("hello")(session, doc, pdf_bytes)

    result = run_ingestion(db, str(document.id), storage=storage, index_fn=index_fn)
    stored = db.get(Document, document.id)

    assert result["status"] == "ready"
    assert result["chunk_count"] == 1
    assert result["total_pages"] == 2
    assert stored is not None
    assert stored.status == DocumentStatus.ready.value
    assert stored.last_error is None
    assert stored.ingestion_stage == "embed"
    assert stored.total_pages == 2
    assert seen["bytes"] == MIN_PDF
    assert str(document.id) not in locks
    assert stored.chunks[0].content == "hello"
    assert stored.chunks[0].access_roles == ["hr", "admin"]


def test_skips_when_indexing_lock_held(db: Session, storage: FakeStorage, locks: set[str]):
    document = _seed(db, storage)
    locks.add(str(document.id))

    result = run_ingestion(db, document.id, storage=storage, index_fn=_index_chunk("hello"))
    stored = db.get(Document, document.id)

    assert result == {"status": "skipped", "document_id": str(document.id), "reason": "locked"}
    assert stored is not None
    assert stored.status == DocumentStatus.pending.value
    assert db.query(DocumentChunk).count() == 0


def test_reingest_replaces_chunks(db: Session, storage: FakeStorage):
    document = _seed(db, storage, chunks=2)
    assert db.query(DocumentChunk).filter_by(document_id=document.id).count() == 2

    run_ingestion(db, document.id, storage=storage, index_fn=_index_chunk("first"))
    run_ingestion(db, document.id, storage=storage, index_fn=_index_chunk("second", pages=4))

    rows = db.query(DocumentChunk).filter_by(document_id=document.id).all()
    stored = db.get(Document, document.id)
    assert len(rows) == 1
    assert rows[0].content == "second"
    assert stored is not None
    assert stored.status == DocumentStatus.ready.value
    assert stored.total_pages == 4


def test_index_failure_sets_last_error_and_deletes_chunks(db: Session, storage: FakeStorage, locks: set[str]):
    document = _seed(db, storage, chunks=1)

    def boom(session: Session, doc: Document, pdf_bytes: bytes) -> IndexResult:
        session.add(
            DocumentChunk(
                document_id=doc.id,
                chunk_id=make_chunk_id(doc.id, 9, 0),
                page_number=9,
                access_roles=list(doc.access_roles),
                content="partial",
                token_count=1,
            )
        )
        session.flush()
        raise RuntimeError("embed boom")

    with pytest.raises(RuntimeError, match="embed boom"):
        run_ingestion(db, document.id, storage=storage, index_fn=boom)

    stored = db.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.failed.value
    assert stored.last_error == "embed boom"
    assert stored.ingestion_stage == "parse"
    assert db.query(DocumentChunk).filter_by(document_id=document.id).count() == 0
    assert str(document.id) not in locks


def test_missing_minio_object_fails(db: Session, storage: FakeStorage):
    document = _seed(db, storage)
    storage.objects.clear()

    with pytest.raises(IngestionError, match="Failed to download object"):
        run_ingestion(db, document.id, storage=storage, index_fn=_index_chunk("hello"))

    stored = db.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.failed.value
    assert stored.last_error is not None
    assert stored.ingestion_stage == "parse"
    assert "download" in stored.last_error.lower()


def test_non_pdf_object_fails(db: Session, storage: FakeStorage):
    document = _seed(db, storage, pdf=b"not-a-pdf")

    with pytest.raises(IngestionError, match="not a PDF"):
        run_ingestion(db, document.id, storage=storage, index_fn=_index_chunk("hello"))

    stored = db.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.failed.value
    assert "not a PDF" in (stored.last_error or "")


def test_missing_document_releases_lock(db: Session, storage: FakeStorage, locks: set[str]):
    missing = uuid4()
    result = run_ingestion(db, missing, storage=storage, index_fn=_index_chunk("hello"))
    assert result["status"] == "error"
    assert result["detail"] == "document not found"
    assert str(missing) not in locks


def test_invalid_document_id_does_not_raise(db: Session):
    result = run_ingestion(db, "not-a-uuid")
    assert result == {"status": "error", "detail": "invalid document_id"}


def test_status_goes_processing_before_ready(db: Session, storage: FakeStorage):
    document = _seed(db, storage)
    seen: list[str] = []

    def index_fn(session: Session, doc: Document, pdf_bytes: bytes) -> IndexResult:
        seen.append(doc.status)
        return IndexResult(chunk_count=0, total_pages=1)

    run_ingestion(db, document.id, storage=storage, index_fn=index_fn)
    assert seen == [DocumentStatus.processing.value]
    stored = db.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.ready.value
    assert stored.total_pages == 1


def test_persist_ingestion_failure_truncates_last_error(db: Session, storage: FakeStorage):
    document = _seed(db, storage)
    persist_ingestion_failure(db, document.id, RuntimeError("x" * 5000))
    stored = db.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.failed.value
    assert stored.last_error is not None
    assert len(stored.last_error) == 2000


def test_index_pdf_rejects_non_pdf(db: Session):
    document = _seed(db, FakeStorage())
    with pytest.raises(IngestionError, match="not a PDF"):
        index_pdf(db, document, b"hello")


def test_index_pdf_blank_pdf_fails(db: Session):
    document = _seed(db, FakeStorage(), pdf=blank_pdf_bytes())
    with pytest.raises(IngestionError, match="no extractable text"):
        index_pdf(db, document, blank_pdf_bytes())
    db.refresh(document)
    assert document.ingestion_stage == "chunk"


def test_index_pdf_advances_parse_chunk_embed_stages(db: Session, monkeypatch):
    seen: list[str] = []
    from app.services import ingestion as ingestion_mod

    original = ingestion_mod.set_ingestion_stage

    def spy(session: Session, document: Document, stage: str) -> None:
        seen.append(stage)
        original(session, document, stage)

    monkeypatch.setattr(ingestion_mod, "set_ingestion_stage", spy)
    document = _seed(db, FakeStorage(), pdf=policy_pdf_bytes())
    ingestion_mod.index_pdf(db, document, policy_pdf_bytes())
    db.flush()
    db.refresh(document)
    assert seen == ["parse", "chunk", "embed"]
    assert document.ingestion_stage == "embed"


def test_index_pdf_persists_page_chunks_acl_and_embeddings(db: Session, stub_embeddings):
    document = _seed(db, FakeStorage(), pdf=policy_pdf_bytes())
    result = index_pdf(db, document, policy_pdf_bytes())
    db.flush()

    rows = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.page_number, DocumentChunk.chunk_id)
        .all()
    )
    assert result.total_pages == 2
    assert result.chunk_count == len(rows)
    assert rows
    assert {row.page_number for row in rows} <= {1, 2}
    assert all(row.access_roles == ["hr", "admin"] for row in rows)
    assert all(row.doc_title == document.title for row in rows)
    assert all("[Document:" not in row.content for row in rows)
    assert any(row.is_table and "Vacation" in row.content and "|" in row.content for row in rows)
    assert any(row.bbox and "page_width" in row.bbox for row in rows)
    assert all(row.embedding is not None and len(row.embedding) == EMBEDDING_DIM for row in rows)
    assert stub_embeddings["texts"]
    assert all(text.startswith("[Document: Policy.pdf |") for text in stub_embeddings["texts"])
    for text in stub_embeddings["texts"]:
        header, body = text.split("\n", 1)
        assert header.startswith("[Document:")
        assert not body.startswith("[Document:")


def test_index_pdf_rejects_wrong_embedding_dim(db: Session, monkeypatch):
    document = _seed(db, FakeStorage(), pdf=policy_pdf_bytes())

    def bad_embed(texts, *, embedder=None):
        return [[0.0] * 8 for _ in texts]

    monkeypatch.setattr("app.services.ingestion.embed_texts", bad_embed)
    with pytest.raises(IngestionError, match="384"):
        index_pdf(db, document, policy_pdf_bytes())


def test_index_pdf_wraps_embedding_error(db: Session, monkeypatch):
    document = _seed(db, FakeStorage(), pdf=policy_pdf_bytes())

    def boom(texts, *, embedder=None):
        raise EmbeddingError("Embedding model not found")

    monkeypatch.setattr("app.services.ingestion.embed_texts", boom)
    with pytest.raises(IngestionError, match="Embedding model not found"):
        index_pdf(db, document, policy_pdf_bytes())


def test_run_ingestion_parser_reingest_does_not_duplicate(db: Session, storage: FakeStorage):
    document = _seed(db, storage, pdf=policy_pdf_bytes())
    run_ingestion(db, document.id, storage=storage)
    first = db.query(DocumentChunk).filter_by(document_id=document.id).count()
    assert first > 0

    run_ingestion(db, document.id, storage=storage)
    rows = db.query(DocumentChunk).filter_by(document_id=document.id).all()
    stored = db.get(Document, document.id)
    assert stored is not None
    assert stored.status == DocumentStatus.ready.value
    assert stored.total_pages == 2
    assert len(rows) == first
    chunk_ids = [row.chunk_id for row in rows]
    assert len(chunk_ids) == len(set(chunk_ids))
    assert all(row.embedding is not None and len(row.embedding) == EMBEDDING_DIM for row in rows)
    assert all(row.access_roles == ["hr", "admin"] for row in rows)
