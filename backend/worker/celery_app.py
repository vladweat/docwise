"""Celery app and `ingestion.process_document` task."""

import logging
import time

from celery import Celery
from celery.schedules import crontab
from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from celery.signals import setup_logging as celery_setup_logging
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging import setup_logging as setup_json_logging
from app.core.redis import release_indexing_lock
from app.core.rls import clear_session_rls
from app.core.sentry import capture_pipeline_error, init_sentry
from app.services.ingestion import persist_ingestion_failure, persist_ingestion_retry, run_ingestion
from app.services.ingestion.indexing import RetryableIngestionError
from app.services.retention import purge_expired_audit_logs
from app.services.storage_deletions import process_storage_deletions

logger = logging.getLogger(__name__)

settings = get_settings()
init_sentry()


@celery_setup_logging.connect
def configure_worker_logging(**_kwargs) -> None:
    """Use the API's JSON formatter for worker events and exception types."""
    setup_json_logging(settings.log_level)

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
    beat_schedule={
        "purge-expired-rag-audit-logs-daily": {
            "task": "maintenance.purge_expired_rag_audit_logs",
            "schedule": crontab(hour=3, minute=15),
        },
        "process-document-storage-deletions-every-five-minutes": {
            "task": "maintenance.process_document_storage_deletions",
            "schedule": crontab(minute="*/5"),
        },
    },
)


@celery_app.task(
    name="ingestion.process_document",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(RetryableIngestionError, SQLAlchemyError, RedisError),
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
    started_at = time.monotonic()
    try:
        logger.info(
            "process_document document_id=%s task_id=%s retries=%s",
            document_id,
            self.request.id,
            self.request.retries,
        )
        result = run_ingestion(db, document_id)
        logger.info(
            "ingestion task finished document_id=%s result=%s duration_ms=%s",
            document_id,
            result.get("status", "unknown"),
            round((time.monotonic() - started_at) * 1000),
        )
        return result
    except Exception as exc:
        retryable = isinstance(exc, (RetryableIngestionError, SQLAlchemyError, RedisError))
        retry_exhausted = self.request.retries >= INGEST_MAX_RETRIES
        retry_scheduled = retryable and not retry_exhausted
        target_state = "retry" if retry_scheduled else "failed"
        state_persisted = True
        try:
            db.rollback()
            if retry_scheduled:
                persist_ingestion_retry(db, document_id)
            else:
                persist_ingestion_failure(db, document_id, exc)
        except Exception as persist_exc:
            state_persisted = False
            logger.error(
                "failed to persist ingestion state document_id=%s error_type=%s",
                document_id,
                type(persist_exc).__name__,
                extra={
                    "event": "ingestion_state_persist_failed",
                    "target_state": target_state,
                    "error_type": type(persist_exc).__name__,
                },
            )
        if retry_scheduled:
            logger.warning(
                "ingestion retry scheduled",
                extra={
                    "event": "ingestion_retry_scheduled",
                    "error_type": type(exc).__name__,
                    "retry_attempt": self.request.retries + 1,
                    "max_retries": INGEST_MAX_RETRIES,
                    "state_persisted": state_persisted,
                },
            )
        else:
            logger.error(
                "ingestion failed permanently",
                extra={
                    "event": "ingestion_failed_permanently",
                    "error_type": type(exc).__name__,
                    "retryable": retryable,
                    "attempt": self.request.retries + 1,
                    "max_retries": INGEST_MAX_RETRIES,
                    "state_persisted": state_persisted,
                },
            )
        # run_ingestion normally releases its lock in finally. This is a safe
        # owner-checked no-op if the failure happened before acquisition.
        release_indexing_lock(document_id)
        logger.error(
            "ingestion task failed document_id=%s error_type=%s retryable=%s retries=%s duration_ms=%s",
            document_id,
            type(exc).__name__,
            retryable,
            self.request.retries,
            round((time.monotonic() - started_at) * 1000),
        )
        capture_pipeline_error("ingestion", RuntimeError(type(exc).__name__))
        raise
    finally:
        clear_session_rls(db)
        db.close()


@celery_app.task(
    name="maintenance.purge_expired_rag_audit_logs",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=INGEST_RETRY_BACKOFF_MAX,
    max_retries=INGEST_MAX_RETRIES,
)
def purge_expired_rag_audit_logs_task() -> dict[str, int]:
    """Remove audit rows beyond the configured retention window."""
    deleted = purge_expired_audit_logs()
    logger.info("purged expired rag audit logs count=%s", deleted)
    return {"deleted": deleted}


@celery_app.task(
    name="maintenance.process_document_storage_deletions",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=INGEST_RETRY_BACKOFF_MAX,
    max_retries=INGEST_MAX_RETRIES,
)
def process_document_storage_deletions_task() -> dict[str, int]:
    """Retry bounded, idempotent MinIO cleanup requests from the database outbox."""
    db: Session = SessionLocal()
    try:
        from app.core.rls import bind_session_rls

        bind_session_rls(db, bypass=True)
        return process_storage_deletions(db)
    finally:
        clear_session_rls(db)
        db.close()
