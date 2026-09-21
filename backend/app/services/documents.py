"""Document upload, ACL-filtered reads, ACL patch, and KB delete. PDF parsing stays in Celery."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

import fitz
from sqlalchemy import String, cast
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    PayloadTooLargeError,
    UnavailableError,
)
from app.core.principal import Principal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.schemas.document import (
    DocumentAccessUpdate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatusResponse,
)
from app.services.document_format import (
    DOCX_MEDIA,
    PDF_MAGIC,
    detect_format,
    media_type_for_title,
    suffix_format,
)
from app.services.docx_parser import estimate_docx_quota_units
from app.services.quotas import enforce_page_quota_for_upload
from app.services.storage import ObjectStorage, StorageError, get_object_storage, object_key_for_document
from app.services.text import InvalidRoleTag, TooManyRoleTags, normalize_role_tags

logger = logging.getLogger(__name__)

NOT_FOUND_DETAIL = "Document not found"
UNSUPPORTED_FORMAT = "Only PDF and DOCX files are supported"
DUPLICATE_HASH_DETAIL = "Document with this file hash already exists"


def enqueue_ingestion(document_id: UUID) -> None:
    from worker.celery_app import process_document_task

    process_document_task.delay(str(document_id))


def acl_overlap(user: Principal):
    return Document.access_roles.overlap(cast(list(user.allowed_roles()), ARRAY(String)))


def visible_documents_query(db: Session, user: Principal):
    return (
        db.query(Document)
        .filter(Document.organization_id == user.organization_id)
        .filter(acl_overlap(user))
    )


def preview_snippet_for_document(db: Session, document: Document) -> str | None:
    row = (
        db.query(DocumentChunk.content)
        .filter(
            DocumentChunk.document_id == document.id,
            DocumentChunk.organization_id == document.organization_id,
        )
        .order_by(DocumentChunk.page_number.asc(), DocumentChunk.chunk_id.asc())
        .first()
    )
    if row is None:
        return None
    snippet = " ".join(str(row[0]).split())
    return snippet[:260] or None


def get_visible_document(db: Session, user: Principal, document_id: UUID) -> Document:
    document = visible_documents_query(db, user).filter(Document.id == document_id).first()
    if document is None:
        raise NotFoundError(NOT_FOUND_DETAIL)
    return document


def get_managed_document(db: Session, user: Principal, document_id: UUID) -> Document:
    """KB write: current org only. Same 404 as missing / other tenant. Does not bypass inner ACL on read."""
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.organization_id == user.organization_id)
        .first()
    )
    if document is None:
        raise NotFoundError(NOT_FOUND_DETAIL)
    return document


def parse_access_roles(raw: list[str] | str | None) -> list[str]:
    if raw is None:
        values: list[str] = []
    elif isinstance(raw, str):
        values = [raw]
    else:
        values = list(raw)

    tokens: list[str] = []
    for item in values:
        piece = item.strip()
        if not piece:
            continue
        if piece.startswith("["):
            try:
                parsed = json.loads(piece)
            except json.JSONDecodeError as exc:
                raise BadRequestError("access_roles must be a JSON list or repeated form fields") from exc
            if not isinstance(parsed, list) or not all(isinstance(entry, str) for entry in parsed):
                raise BadRequestError("access_roles must be a list of strings")
            tokens.extend(parsed)
            continue
        if "," in piece:
            tokens.extend(part.strip() for part in piece.split(","))
            continue
        tokens.append(piece)

    try:
        normalized = normalize_role_tags(tokens)
    except InvalidRoleTag as exc:
        raise BadRequestError("Invalid access_roles value") from exc
    except TooManyRoleTags as exc:
        raise BadRequestError("Too many access_roles") from exc

    if not normalized:
        raise BadRequestError("access_roles is required")
    return normalized


def count_pdf_pages(content: bytes) -> int:
    """Page count only — no text extraction. Used to reserve plan quota at upload."""
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise BadRequestError(UNSUPPORTED_FORMAT) from exc
    try:
        pages = int(pdf.page_count)
    finally:
        pdf.close()
    if pages < 1:
        raise BadRequestError(UNSUPPORTED_FORMAT)
    return pages


def quota_units_for_upload(filename: str, content: bytes, file_kind: str) -> int:
    if file_kind == "docx":
        return estimate_docx_quota_units(content)
    return count_pdf_pages(content)


def validate_document_upload(
    filename: str,
    content: bytes,
    content_type: str | None,
    max_bytes: int,
) -> str:
    """Return ``pdf`` or ``docx`` when valid."""
    if not content:
        raise BadRequestError("Empty file")
    if len(content) > max_bytes:
        raise PayloadTooLargeError("File exceeds size limit")
    kind = detect_format(filename, content, content_type)
    if kind is None:
        raise BadRequestError(UNSUPPORTED_FORMAT)
    media = (content_type or "").split(";")[0].strip().lower()
    if kind == "pdf" and media and media not in {"application/pdf", "application/octet-stream"}:
        raise BadRequestError(UNSUPPORTED_FORMAT)
    if kind == "docx" and media and media not in {DOCX_MEDIA, "application/octet-stream"}:
        raise BadRequestError(UNSUPPORTED_FORMAT)
    if kind == "pdf" and not content.startswith(PDF_MAGIC):
        raise BadRequestError(UNSUPPORTED_FORMAT)
    return kind


def _title_from_filename(filename: str, *, default_ext: str = ".pdf") -> str:
    name = Path(filename).name.strip() or f"document{default_ext}"
    return name[:512]


def create_document_from_upload(
    db: Session,
    *,
    user: Principal,
    filename: str,
    content: bytes,
    content_type: str | None,
    access_roles_raw: list[str] | str | None,
    storage: ObjectStorage | None = None,
) -> Document:
    settings = get_settings()
    file_kind = validate_document_upload(filename, content, content_type, settings.upload_max_bytes)
    access_roles = parse_access_roles(access_roles_raw)
    incoming_pages = quota_units_for_upload(filename, content, file_kind)
    digest = hashlib.sha256(content).hexdigest()
    org_id = user.organization_id

    existing = (
        db.query(Document.id)
        .filter(Document.organization_id == org_id, Document.file_hash == digest)
        .first()
    )
    if existing is not None:
        raise ConflictError(DUPLICATE_HASH_DETAIL)

    enforce_page_quota_for_upload(db, org_id, incoming_pages)

    document_id = uuid4()
    default_ext = ".docx" if file_kind == "docx" else ".pdf"
    title = _title_from_filename(filename, default_ext=default_ext)
    key = object_key_for_document(document_id, filename, organization_id=org_id)
    storage = storage or get_object_storage()
    stored_media = DOCX_MEDIA if file_kind == "docx" else "application/pdf"

    try:
        storage.put_bytes(key, content, content_type=stored_media)
    except StorageError as exc:
        logger.warning("MinIO put failed document_id=%s", document_id)
        raise UnavailableError("Object storage unavailable") from exc

    document = Document(
        id=document_id,
        organization_id=org_id,
        title=title,
        file_path=key,
        file_hash=digest,
        file_size_bytes=len(content),
        total_pages=incoming_pages,
        access_roles=access_roles,
        status=DocumentStatus.pending.value,
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        try:
            storage.delete_object(key)
        except StorageError:
            logger.warning("MinIO cleanup failed after hash conflict key=%s", key)
        duplicate = (
            db.query(Document.id)
            .filter(Document.organization_id == org_id, Document.file_hash == digest)
            .first()
        )
        if duplicate is not None:
            raise ConflictError(DUPLICATE_HASH_DETAIL)
        raise
    db.refresh(document)

    try:
        enqueue_ingestion(document.id)
    except Exception as exc:
        logger.warning("Celery enqueue failed document_id=%s: %s", document.id, exc)
        db.delete(document)
        db.commit()
        try:
            storage.delete_object(key)
        except StorageError:
            logger.warning("MinIO cleanup failed after enqueue error key=%s", key)
        raise UnavailableError("Ingestion queue unavailable") from exc

    logger.info(
        "document uploaded id=%s size=%s pages=%s roles=%s",
        document.id,
        document.file_size_bytes,
        incoming_pages,
        access_roles,
    )
    return document


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
    from app.services.llm_cache import invalidate_llm_cache

    invalidate_llm_cache(db, document.organization_id)
    db.commit()
    db.refresh(document)
    logger.info("document ACL updated id=%s roles=%s", document.id, roles)
    return document


def delete_document(
    db: Session,
    user: Principal,
    document_id: UUID,
    storage: ObjectStorage | None = None,
) -> None:
    document = get_managed_document(db, user, document_id)

    storage = storage or get_object_storage()
    key = document.file_path
    org_id = document.organization_id

    from app.services.llm_cache import invalidate_llm_cache

    db.delete(document)
    invalidate_llm_cache(db, org_id)
    db.commit()

    try:
        storage.delete_object(key)
    except StorageError:
        logger.warning("MinIO delete failed after document row removed document_id=%s", document_id)

    logger.info("document deleted id=%s", document_id)
