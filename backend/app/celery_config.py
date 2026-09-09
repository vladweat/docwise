import logging

from celery import Celery

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app.core.config import get_settings
from app.core.sentry import capture_pipeline_error, init_sentry

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
    """Placeholder until Milestone 1 wires PDF ingest."""
    try:
        logger.info("process_document stub document_id=%s task_id=%s", document_id, self.request.id)
        return {"status": "stub", "document_id": document_id}
    except Exception as exc:
        capture_pipeline_error("ingestion", exc)
        raise
