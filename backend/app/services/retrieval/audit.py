"""RAG audit trail: query, user, chunk UUIDs, latency, tokens, feedback.

Never persist chunk body text. Audit rows may later be readable by the same user.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import RagAuditLog

logger = logging.getLogger(__name__)


def chunk_ids_for_audit(chunk_ids: Sequence[object] | None) -> list[str]:
    """Keep UUID strings only. Drop anything that looks like chunk text."""
    out: list[str] = []
    seen: set[str] = set()
    for item in chunk_ids or []:
        text = str(item).strip()
        if not text:
            continue
        try:
            canonical = str(UUID(text))
        except ValueError:
            logger.warning("dropping non-uuid value from rag_audit_logs.retrieved_chunk_ids")
            continue
        if canonical in seen:
            continue
        seen.add(canonical)
        out.append(canonical)
    return out


def record_retrieval_audit(
    db: Session,
    *,
    user_id: UUID,
    query: str,
    retrieved_chunk_ids: Sequence[object] | None = None,
    latency_ms: int | None = None,
    tokens_used: int | None = None,
    session_id: UUID | None = None,
    message_id: UUID | None = None,
    organization_id: UUID,
    commit: bool = True,
) -> RagAuditLog:
    """Append audit row with chunk UUIDs only (no excerpt text)."""
    log = RagAuditLog(
        organization_id=organization_id,
        user_id=user_id,
        session_id=session_id,
        message_id=message_id,
        query=query,
        retrieved_chunk_ids=chunk_ids_for_audit(retrieved_chunk_ids),
        latency_ms=latency_ms,
        tokens_used=tokens_used,
    )
    db.add(log)
    if commit:
        db.commit()
        db.refresh(log)
    return log
