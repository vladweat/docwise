"""Celery entry: lock, download, run indexer, status machine."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.redis import acquire_indexing_lock, release_indexing_lock
from app.core.rls import bind_session_rls
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.ingestion.format import detect_format
from app.services.ingestion.indexing import IndexFn, IngestionError, index_docx, index_pdf
from app.services.ingestion.stages import LAST_ERROR_MAX_LEN, STAGE_EMBED, STAGE_PARSE
from app.services.org.quotas import IngestionQuotaError, assert_ingest_pages_allowed
from app.services.storage import ObjectStorage, StorageError, get_object_storage

logger = logging.getLogger(__name__)


def fetch_document_for_ingestion(db: Session, document_id: UUID) -> Document | None:
    """Bypass RLS only for primary-key lookup, then bind the document's org."""
    bind_session_rls(db, bypass=True)
    document = db.get(Document, document_id)
    if document is None:
        bind_session_rls(db, bypass=False)
        return None
    bind_session_rls(db, organization_id=document.organization_id)
    return document


def delete_chunks_for_document(db: Session, document_id: UUID) -> int:
    """Drop every chunk for `document_id`. Used before insert and on rollback."""
    deleted = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


def persist_ingestion_failure(db: Session, document_id: str | UUID, exc: BaseException) -> None:
    """`failed` + `last_error`, and delete any leftover chunks (no half-ready index)."""
    try:
        doc_uuid = document_id if isinstance(document_id, UUID) else UUID(str(document_id))
    except (ValueError, TypeError, AttributeError):
        return
    db.rollback()
    document = fetch_document_for_ingestion(db, doc_uuid)
    if document is None:
        return
    delete_chunks_for_document(db, doc_uuid)
    document.status = DocumentStatus.failed.value
    document.last_error = str(exc)[:LAST_ERROR_MAX_LEN]
    db.commit()
    logger.warning(
        "ingestion failed document_id=%s error=%s",
        doc_uuid,
        document.last_error,
    )


def _indexer_for_bytes(filename: str, content: bytes) -> IndexFn:
    kind = detect_format(filename, content, None)
    if kind == "docx":
        return index_docx
    return index_pdf


def run_ingestion(
    db: Session,
    document_id: str | UUID,
    *,
    storage: ObjectStorage | None = None,
    index_fn: IndexFn | None = None,
) -> dict:
    """Process one document. Safe to retry: lock + delete-then-insert chunks."""
    try:
        doc_uuid = document_id if isinstance(document_id, UUID) else UUID(str(document_id))
    except (ValueError, TypeError, AttributeError):
        logger.error("invalid document_id=%s", document_id)
        return {"status": "error", "detail": "invalid document_id"}

    if not acquire_indexing_lock(doc_uuid):
        logger.info("ingestion skipped document_id=%s reason=locked", doc_uuid)
        return {"status": "skipped", "document_id": str(doc_uuid), "reason": "locked"}

    try:
        document = fetch_document_for_ingestion(db, doc_uuid)
        if document is None:
            logger.error("document %s not found", doc_uuid)
            return {"status": "error", "detail": "document not found", "document_id": str(doc_uuid)}

        document.status = DocumentStatus.processing.value
        document.last_error = None
        document.ingestion_stage = STAGE_PARSE
        db.commit()

        storage = storage or get_object_storage()
        try:
            file_bytes = storage.get_bytes(document.file_path)
        except StorageError as exc:
            raise IngestionError(f"Failed to download object: {exc}") from exc

        if not file_bytes:
            raise IngestionError("Downloaded object is empty")
        kind = detect_format(document.title, file_bytes, None)
        if kind is None:
            raise IngestionError("Unsupported document format")
        indexer = index_fn or (_indexer_for_bytes(document.title, file_bytes))

        logger.info(
            "downloaded document_id=%s bytes=%s key=%s format=%s",
            document.id,
            len(file_bytes),
            document.file_path,
            kind,
        )

        delete_chunks_for_document(db, document.id)
        result = indexer(db, document, file_bytes)
        if result.total_pages is not None:
            document.total_pages = result.total_pages
        db.flush()
        if result.total_pages is not None:
            assert_ingest_pages_allowed(
                db,
                document.organization_id,
                result.total_pages,
                exclude_document_id=document.id,
            )
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .count()
        )
        document.status = DocumentStatus.ready.value
        document.last_error = None
        document.ingestion_stage = STAGE_EMBED
        from app.services.chat.llm_cache import invalidate_llm_cache

        invalidate_llm_cache(db, document.organization_id)
        db.commit()

        logger.info(
            "ingestion ready document_id=%s pages=%s chunks=%s",
            document.id,
            document.total_pages,
            chunk_count,
        )
        return {
            "status": "ready",
            "document_id": str(document.id),
            "chunk_count": chunk_count,
            "total_pages": document.total_pages,
        }
    except IngestionQuotaError as exc:
        persist_ingestion_failure(db, doc_uuid, exc)
        failed = db.get(Document, doc_uuid)
        if failed is not None and storage is not None:
            try:
                storage.delete_object(failed.file_path)
            except StorageError:
                logger.warning("MinIO cleanup failed after page quota document_id=%s", doc_uuid)
        logger.warning("ingestion page quota exceeded document_id=%s", doc_uuid)
        return {
            "status": "failed",
            "document_id": str(doc_uuid),
            "detail": str(exc),
        }
    except Exception as exc:
        persist_ingestion_failure(db, doc_uuid, exc)
        raise
    finally:
        release_indexing_lock(doc_uuid)
