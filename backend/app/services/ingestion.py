"""Celery ingestion worker: lock, MinIO download, status machine, idempotent re-run.

Parse + page-bounded chunking run here. FastEmbed upsert is the next M1 item
(`embedding` stays null until then). This module owns
`pending → processing → ready | failed`, the Redis lock, and rollback of chunks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id
from app.services.chunker import chunk_parsed_document
from app.services.pdf_parser import PdfParserError, parse_pdf
from app.services.storage import ObjectStorage, StorageError, get_object_storage
from app.utils.redis_lock import acquire_indexing_lock, release_indexing_lock

logger = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
LAST_ERROR_MAX_LEN = 2000


class IngestionError(Exception):
    """Download or indexing failed; the worker maps this to `failed` + `last_error`."""


@dataclass(frozen=True)
class IndexResult:
    chunk_count: int
    total_pages: int | None = None


IndexFn = Callable[[Session, Document, bytes], IndexResult]


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
    document = db.get(Document, doc_uuid)
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


def index_pdf(db: Session, document: Document, pdf_bytes: bytes) -> IndexResult:
    """Replace `document_chunks` for this PDF. Must not commit; the worker commits.

    `content` is the UI/LLM fragment (no meta header). Embeddings are filled
    later from `PreparedChunk.embed_text`; they stay null in this step.
    """
    if not pdf_bytes.startswith(PDF_MAGIC):
        raise IngestionError("Downloaded object is not a PDF")
    try:
        parsed = parse_pdf(pdf_bytes)
    except PdfParserError as exc:
        raise IngestionError(str(exc)) from exc

    chunks = chunk_parsed_document(parsed)
    if not chunks:
        raise IngestionError("PDF produced no extractable text")

    ordinal_by_page: dict[int, int] = {}
    roles = list(document.access_roles)
    for chunk in chunks:
        ordinal = ordinal_by_page.get(chunk.page_number, 0)
        ordinal_by_page[chunk.page_number] = ordinal + 1
        db.add(
            DocumentChunk(
                document_id=document.id,
                chunk_id=make_chunk_id(document.id, chunk.page_number, ordinal),
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                is_table=chunk.is_table,
                access_roles=list(roles),
                content=chunk.content,
                token_count=chunk.token_count,
                embedding=None,
                doc_title=document.title,
                bbox=chunk.bbox,
                highlight_rects=chunk.highlight_rects,
            )
        )
    return IndexResult(chunk_count=len(chunks), total_pages=parsed.total_pages)


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

    indexer = index_fn or index_pdf
    try:
        document = db.get(Document, doc_uuid)
        if document is None:
            logger.error("document %s not found", doc_uuid)
            return {"status": "error", "detail": "document not found", "document_id": str(doc_uuid)}

        document.status = DocumentStatus.processing.value
        document.last_error = None
        db.commit()

        storage = storage or get_object_storage()
        try:
            pdf_bytes = storage.get_bytes(document.file_path)
        except StorageError as exc:
            raise IngestionError(f"Failed to download object: {exc}") from exc

        if not pdf_bytes:
            raise IngestionError("Downloaded object is empty")
        if not pdf_bytes.startswith(PDF_MAGIC):
            raise IngestionError("Downloaded object is not a PDF")

        logger.info(
            "downloaded document_id=%s bytes=%s key=%s",
            document.id,
            len(pdf_bytes),
            document.file_path,
        )

        delete_chunks_for_document(db, document.id)
        result = indexer(db, document, pdf_bytes)
        if result.total_pages is not None:
            document.total_pages = result.total_pages
        db.flush()
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document.id)
            .count()
        )
        document.status = DocumentStatus.ready.value
        document.last_error = None
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
    except Exception as exc:
        persist_ingestion_failure(db, doc_uuid, exc)
        raise
    finally:
        release_indexing_lock(doc_uuid)
