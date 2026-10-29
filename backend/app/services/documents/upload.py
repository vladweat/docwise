"""Upload validation, quota reservation, and document row creation."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from uuid import UUID, uuid4

import fitz
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    PayloadTooLargeError,
    UnavailableError,
)
from app.core.principal import Principal
from app.models.document import Document, DocumentStatus
from app.models.storage_deletion import StorageDeletion
from app.services.ingestion.format import DOCX_MEDIA, PDF_MAGIC, detect_format
from app.services.documents.acl import parse_access_roles
from app.services.ingestion.docx_parser import estimate_docx_quota_units
from app.services.org.quotas import enforce_page_quota_for_upload
from app.services.storage import ObjectStorage, StorageError, get_object_storage, object_key_for_document

logger = logging.getLogger(__name__)

UNSUPPORTED_FORMAT = "Only PDF and DOCX files are supported"
DUPLICATE_HASH_DETAIL = "Document with this file hash already exists"


def enqueue_ingestion(document_id: UUID) -> None:
    """Dispatch Celery `ingestion.process_document` for one UUID."""
    from worker.celery_app import process_document_task

    process_document_task.delay(str(document_id))


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
    """Persist upload in session org, reserve page quota, enqueue ingest (no parse in the handler)."""
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
        duplicate = (
            db.query(Document.id)
            .filter(Document.organization_id == org_id, Document.file_hash == digest)
            .first()
        )
        db.add(StorageDeletion(object_key=key))
        db.commit()
        if duplicate is not None:
            raise ConflictError(DUPLICATE_HASH_DETAIL)
        raise
    db.refresh(document)

    try:
        enqueue_ingestion(document.id)
    except Exception as exc:
        logger.warning("Celery enqueue failed document_id=%s error_type=%s", document.id, type(exc).__name__)
        db.add(StorageDeletion(object_key=key))
        db.delete(document)
        db.commit()
        raise UnavailableError("Ingestion queue unavailable") from exc

    logger.info(
        "document uploaded id=%s size=%s pages=%s roles=%s",
        document.id,
        document.file_size_bytes,
        incoming_pages,
        access_roles,
    )
    return document
