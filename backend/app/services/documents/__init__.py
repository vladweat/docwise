"""Document upload, ACL-filtered reads, ACL patch, and KB delete. PDF parsing stays in Celery."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.principal import Principal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.storage_deletion import StorageDeletion
from app.schemas.document import (
    DocumentAccessUpdate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.services.ingestion.format import media_type_for_title, suffix_format
from app.services.documents.acl import (
    NOT_FOUND_DETAIL,
    get_managed_document,
    get_visible_document,
    parse_access_roles,
    preview_snippet_for_document,
    visible_documents_query,
)
from app.services.documents.upload import create_document_from_upload, enqueue_ingestion
from app.services.storage import ObjectStorage, StorageError, get_object_storage

logger = logging.getLogger(__name__)


def document_response(db: Session, document: Document) -> DocumentResponse:
    return DocumentResponse.model_validate(
        {
            "id": document.id,
            "title": document.title,
            "content_format": content_format_for_title(document.title),
            "file_size_bytes": document.file_size_bytes,
            "total_pages": document.total_pages,
            "access_roles": list(document.access_roles or []),
            "status": document.status,
            "last_error": document.last_error,
            "preview_snippet": preview_snippet_for_document(db, document),
            "created_at": document.created_at,
        }
    )


def list_documents(
    db: Session,
    user: Principal,
    *,
    limit: int,
    offset: int,
    status_filter: DocumentStatus | None = None,
) -> DocumentListResponse:
    """Paginated KB list for the session org after document ACL filter."""
    query = visible_documents_query(db, user)
    if status_filter is not None:
        query = query.filter(Document.status == status_filter.value)
    total = query.count()
    rows = (
        query.order_by(Document.created_at.desc(), Document.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return DocumentListResponse(
        items=[
            document_response(db, row)
            for row in rows
        ],
        total=int(total),
        limit=limit,
        offset=offset,
    )


def document_status(db: Session, user: Principal, document_id: UUID) -> DocumentStatusResponse:
    document = get_visible_document(db, user, document_id)
    return DocumentStatusResponse(
        id=document.id,
        status=document.status,
        last_error=document.last_error,
        stage=document.ingestion_stage,
    )


def document_raw_bytes(
    db: Session,
    user: Principal,
    document_id: UUID,
    storage: ObjectStorage | None = None,
) -> tuple[bytes, str, str]:
    """Fetch object bytes only after the same org + ACL check as search."""
    document = get_visible_document(db, user, document_id)
    storage = storage or get_object_storage()
    try:
        data = storage.get_bytes(document.file_path)
    except StorageError as exc:
        logger.warning("MinIO get failed document_id=%s", document_id)
        raise NotFoundError(NOT_FOUND_DETAIL) from exc
    return data, document.title, media_type_for_title(document.title)


def content_format_for_title(title: str) -> str:
    return suffix_format(title) or "pdf"


def update_document_access_roles(
    db: Session,
    user: Principal,
    document_id: UUID,
    payload: DocumentAccessUpdate,
) -> Document:
    """Set document ACL and copy it onto every chunk. Does not re-embed. Org does not change."""
    document = get_managed_document(db, user, document_id)

    roles = parse_access_roles(payload.access_roles)
    document.access_roles = list(roles)
    (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.organization_id == document.organization_id,
        )
        .update({DocumentChunk.access_roles: list(roles)}, synchronize_session=False)
    )
    from app.services.chat.llm_cache import invalidate_llm_cache

    invalidate_llm_cache(db, document.organization_id)
    db.commit()
    db.refresh(document)
    logger.info("document ACL updated id=%s roles=%s", document.id, roles)
    return document


def delete_document(
    db: Session,
    user: Principal,
    document_id: UUID,
) -> None:
    """Delete relational content and durably queue object cleanup in one transaction."""
    document = get_managed_document(db, user, document_id)

    key = document.file_path
    org_id = document.organization_id

    from app.services.chat.llm_cache import invalidate_llm_cache

    cleanup = StorageDeletion(object_key=key)
    db.add(cleanup)
    db.delete(document)
    invalidate_llm_cache(db, org_id)
    db.commit()
    logger.info("document deleted; object cleanup queued document_id=%s cleanup_id=%s", document_id, cleanup.id)


__all__ = [
    "create_document_from_upload",
    "delete_document",
    "document_raw_bytes",
    "document_response",
    "document_status",
    "enqueue_ingestion",
    "get_managed_document",
    "get_visible_document",
    "list_documents",
    "parse_access_roles",
    "update_document_access_roles",
]
