"""Bounded cleanup jobs for data with an explicit retention policy."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.audit import RagAuditLog

PURGE_BATCH_SIZE = 1000


def purge_expired_audit_logs(*, now: datetime | None = None) -> int:
    """Delete retrieval-audit rows older than configured retention in bounded transactions."""
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    cutoff = current_time - timedelta(days=get_settings().audit_log_retention_days)
    deleted_total = 0
    db = SessionLocal()
    try:
        while True:
            expired_ids = list(
                db.scalars(
                    select(RagAuditLog.id)
                    .where(RagAuditLog.created_at < cutoff)
                    .order_by(RagAuditLog.created_at)
                    .limit(PURGE_BATCH_SIZE)
                )
            )
            if not expired_ids:
                break
            db.execute(delete(RagAuditLog).where(RagAuditLog.id.in_(expired_ids)))
            db.commit()
            deleted_total += len(expired_ids)
        return deleted_total
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
