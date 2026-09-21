"""Ingestion stage markers for status polling."""

from sqlalchemy.orm import Session

from app.models.document import Document

LAST_ERROR_MAX_LEN = 2000
STAGE_PARSE = "parse"
STAGE_CHUNK = "chunk"
STAGE_EMBED = "embed"


def set_ingestion_stage(db: Session, document: Document, stage: str) -> None:
    """Commit the current parse/chunk/embed step so GET /status can poll it."""
    document.ingestion_stage = stage
    db.commit()
