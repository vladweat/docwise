"""Admin search inspect: pipeline stage lists with the same SQL ACL as chat."""

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.schemas.search import InspectHit, SearchInspectResponse
from app.services.audit import record_retrieval_audit
from app.services.retrieval import StageHit, retrieve

logger = logging.getLogger(__name__)


def inspect_search(
    db: Session,
    user: Principal,
    query: str,
    *,
    limit: int = 15,
    embedder=None,
    reranker=None,
) -> SearchInspectResponse:
    started = time.perf_counter()
    result = retrieve(db, user, query, embedder=embedder, reranker=reranker)
    payload = SearchInspectResponse(
        dense=_hits(result.dense, limit),
        sparse=_hits(result.sparse, limit),
        rrf=_hits(result.rrf, limit),
        reranked=_hits(result.reranked, limit),
    )
    try:
        record_retrieval_audit(
            db,
            organization_id=user.organization_id,
            user_id=user.id,
            query=query,
            retrieved_chunk_ids=[chunk.id for chunk in result.chunks],
            latency_ms=max(int((time.perf_counter() - started) * 1000), 0),
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to persist inspect audit")
    return payload


def _hits(rows: list[StageHit], limit: int) -> list[InspectHit]:
    return [
        InspectHit(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            page=row.page,
            score=row.score,
            snippet=row.snippet,
        )
        for row in rows[:limit]
    ]
