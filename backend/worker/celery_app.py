import logging

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from sqlalchemy.orm import Session

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.rls import clear_session_rls
from app.core.redis import release_indexing_lock
from app.core.sentry import capture_pipeline_error, init_sentry
from app.services.ingestion import persist_ingestion_failure, run_ingestion

logger = logging.getLogger(__name__)

settings = get_settings()
init_sentry()

# Long CPU work (parse + FastEmbed). acks_late + prefetch=1 so a hung embed
# does not hold extra reserved tasks; the lock is per document UUID.
INGEST_SOFT_TIME_LIMIT = 20 * 60
INGEST_TIME_LIMIT = 25 * 60
INGEST_MAX_RETRIES = 3
INGEST_RETRY_BACKOFF_MAX = 10 * 60

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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=INGEST_TIME_LIMIT,
    task_soft_time_limit=INGEST_SOFT_TIME_LIMIT,
    task_default_retry_delay=30,
)


@celery_app.task(
    name="ingestion.process_document",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    dont_autoretry_for=(SoftTimeLimitExceeded, TimeLimitExceeded),
    retry_backoff=True,
    retry_backoff_max=INGEST_RETRY_BACKOFF_MAX,
    retry_jitter=True,
    max_retries=INGEST_MAX_RETRIES,
    soft_time_limit=INGEST_SOFT_TIME_LIMIT,
    time_limit=INGEST_TIME_LIMIT,
)
def process_document_task(self, document_id: str) -> dict:
    """Index one document. `document_id` is a UUID string (not ChainWise int)."""
    db: Session = SessionLocal()
    try:
        logger.info(
            "process_document document_id=%s task_id=%s retries=%s",
            document_id,
            self.request.id,
            self.request.retries,
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
        clear_session_rls(db)
        db.close()
