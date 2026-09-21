"""Celery ingestion: lock, MinIO download, status machine, idempotent re-run."""

from app.services.ingestion.indexing import (
    IndexFn,
    IndexResult,
    IngestionError,
    index_docx,
    index_pdf,
)
from app.services.ingestion.stages import (
    LAST_ERROR_MAX_LEN,
    STAGE_CHUNK,
    STAGE_EMBED,
    STAGE_PARSE,
    set_ingestion_stage,
)
from app.services.ingestion.worker import (
    delete_chunks_for_document,
    persist_ingestion_failure,
    run_ingestion,
)

__all__ = [
    "IndexFn",
    "IndexResult",
    "IngestionError",
    "LAST_ERROR_MAX_LEN",
    "STAGE_CHUNK",
    "STAGE_EMBED",
    "STAGE_PARSE",
    "delete_chunks_for_document",
    "index_docx",
    "index_pdf",
    "persist_ingestion_failure",
    "run_ingestion",
    "set_ingestion_stage",
]
