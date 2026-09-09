import logging

from celery import Celery
from sqlalchemy.orm import Session

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.sentry import capture_pipeline_error, init_sentry
from app.services.ingestion import persist_ingestion_failure, run_ingestion
from app.utils.redis_lock import release_indexing_lock

logger = logging.getLogger(__name__)

settings = get_settings()
init_sentry()

celery_app = Celery(
    "docwise",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)


@celery_app.task(name="ingestion.process_document", bind=True)
def process_document_task(self, document_id: str) -> dict:
    """Index one document. `document_id` is a UUID string (not ChainWise int)."""
    db: Session = SessionLocal()
    try:
        logger.info(
            "process_document document_id=%s task_id=%s",
            document_id,
            self.request.id,
        )
        return run_ingestion(db, document_id)
    except Exception as exc:
        db.rollback()
        try:
            persist_ingestion_failure(db, document_id, exc)
        except Exception:
            logger.exception("failed to persist last_error document_id=%s", document_id)
        release_indexing_lock(document_id)
        logger.exception("Failed to ingest document %s: %s", document_id, exc)
        capture_pipeline_error("ingestion", exc)
        raise
    finally:
        db.close()
