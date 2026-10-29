"""Retryable cleanup for object keys whose document rows were deleted."""

from __future__ import annotations

import logging
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.storage_deletion import StorageDeletion
from app.services.storage import ObjectStorage, get_object_storage

logger = logging.getLogger(__name__)


def process_storage_deletions(db: Session, *, batch_size: int = 100) -> dict[str, int]:
    """Delete a bounded batch of objects; keep failed records for the next run."""
    rows = (
        db.query(StorageDeletion.id, StorageDeletion.object_key)
        .order_by(StorageDeletion.created_at, StorageDeletion.id)
        .limit(batch_size)
        .all()
    )
    candidates = [(row.id, row.object_key) for row in rows]
    db.rollback()

    storage: ObjectStorage = get_object_storage()
    deleted = 0
    failed = 0
    for deletion_id, object_key in candidates:
        try:
            storage.delete_object(object_key)
        except Exception as exc:
            db.query(StorageDeletion).filter(StorageDeletion.id == deletion_id).update(
                {
                    StorageDeletion.attempts: StorageDeletion.attempts + 1,
                    StorageDeletion.last_attempt_at: func.now(),
                },
                synchronize_session=False,
            )
            db.commit()
            failed += 1
            logger.warning(
                "storage deletion failed cleanup_id=%s error_type=%s",
                deletion_id,
                type(exc).__name__,
            )
            continue

        removed = (
            db.query(StorageDeletion)
            .filter(StorageDeletion.id == deletion_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        if removed:
            deleted += 1

    return {"deleted": deleted, "failed": failed, "remaining": max(0, len(candidates) - deleted)}
