"""Document visibility queries and access_roles parsing."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import String, cast
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.core.errors import BadRequestError, NotFoundError
from app.core.principal import Principal
from app.models.document import Document, DocumentChunk
from app.services.text import InvalidRoleTag, TooManyRoleTags, normalize_role_tags

NOT_FOUND_DETAIL = "Document not found"


def acl_overlap(user: Principal):
    """SQL `access_roles && allowed_roles` for the current membership."""
    return Document.access_roles.overlap(cast(list(user.allowed_roles()), ARRAY(String)))


def visible_documents_query(db: Session, user: Principal):
    """Documents in session org the caller may list or download (org + inner ACL)."""
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
    """Single document or NotFound — same 404 for missing, foreign org, or ACL deny."""
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
    """Normalize upload/form ACL tags; reject empty or invalid role tokens."""
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
