"""Corpus hybrid retrieval with SQL RBAC.

Dense pgvector Top-25 + independent Postgres FTS Top-25 (ADR-005), both with
`organization_id` and `access_roles && allowed_roles`, then RRF k=60 and
cross-encoder rerank. Never scrolls the chunk table into RAM.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.ingestion.embeddings import embed_texts
from app.services.retrieval.search import dense_search, hybrid_search, sparse_search
from app.services.retrieval.types import (
    DENSE_TOP_K,
    NO_CONTEXT_ANSWER,
    RERANK_TOP_K,
    RRF_K,
    RRF_TOP_K,
    SNIPPET_LEN,
    SPARSE_TOP_K,
    ChunkRecord,
    HybridPool,
    RetrievalError,
    RetrievalResult,
    RetrievedChunk,
    StageHit,
    allowed_roles_for,
    bm25_scores,
    reciprocal_rank_fusion,
)

logger = logging.getLogger(__name__)


def _stage_hit(record: ChunkRecord, score: float) -> StageHit:
    text = " ".join((record.content or "").split())
    if len(text) > SNIPPET_LEN:
        text = text[: SNIPPET_LEN - 1].rstrip() + "…"
    return StageHit(
        chunk_id=record.chunk_id,
        document_id=record.document_id,
        page=record.page_number,
        score=score,
        snippet=text,
        section_title=record.section_title,
    )


def _retrieved(record: ChunkRecord, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        id=record.id,
        document_id=record.document_id,
        chunk_id=record.chunk_id,
        doc_title=record.doc_title,
        page_number=record.page_number,
        content=record.content,
        access_roles=record.access_roles,
        score=score,
        section_title=record.section_title,
        is_table=record.is_table,
        dense_distance=record.dense_distance,
    )


def embed_query(query: str, *, embedder=None) -> list[float]:
    """FastEmbed of the question. Must not run while a DB session is held."""
    try:
        vectors = embed_texts([query.strip()], embedder=embedder)
    except Exception as exc:
        raise RetrievalError(f"Query embedding failed: {exc}") from exc
    if not vectors:
        raise RetrievalError("Query embedding returned no vector")
    return vectors[0]


def finish_retrieval(
    query: str,
    pool: HybridPool,
    *,
    reranker=None,
) -> RetrievalResult:
    """Cross-encoder rerank. Must not run while a DB session is held."""
    allowed = pool.allowed_roles
    blank = RetrievalResult(
        chunks=[],
        dense=list(pool.dense),
        sparse=list(pool.sparse),
        rrf=list(pool.rrf),
        rerank_scored=[],
        rerank_thresholded=[],
        reranked=[],
        allowed_roles=allowed,
    )
    fused_records = [pool.records[cid] for cid, _score in pool.fused if cid in pool.records]
    if not fused_records:
        return blank

    scored = _rerank_records(query, fused_records, reranker)
    rerank_scored = [_stage_hit(record, score) for record, score in scored]
    threshold = get_settings().rerank_threshold
    thresholded = [(record, score) for record, score in scored if score >= threshold]
    rerank_thresholded = [_stage_hit(record, score) for record, score in thresholded]
    kept = thresholded[:RERANK_TOP_K]
    if not kept:
        logger.info("retrieval refuse: empty after rerank threshold=%.3f", threshold)
        return RetrievalResult(
            chunks=[],
            dense=list(pool.dense),
            sparse=list(pool.sparse),
            rrf=list(pool.rrf),
            rerank_scored=rerank_scored,
            rerank_thresholded=rerank_thresholded,
            reranked=[],
            allowed_roles=allowed,
        )

    reranked_hits = [_stage_hit(record, score) for record, score in kept]
    result_chunks = [_retrieved(record, score) for record, score in kept]
    return RetrievalResult(
        chunks=result_chunks,
        dense=list(pool.dense),
        sparse=list(pool.sparse),
        rrf=list(pool.rrf),
        rerank_scored=rerank_scored,
        rerank_thresholded=rerank_thresholded,
        reranked=reranked_hits,
        allowed_roles=allowed,
    )


def retrieve(
    db: Session,
    user,
    query: str,
    *,
    embedder=None,
    reranker=None,
) -> RetrievalResult:
    """Hybrid search for the authenticated membership. Org and roles come from `user`, not the body.

    Inspect and eval may call this as one step. Chat embeds and reranks with no Session open.
    """
    allowed = allowed_roles_for(user)
    blank = RetrievalResult(chunks=[], allowed_roles=tuple(allowed))
    if not (query or "").strip():
        return blank

    vector = embed_query(query, embedder=embedder)
    pool = hybrid_search(db, user, query, vector)
    return finish_retrieval(query, pool, reranker=reranker)


def _rerank_records(
    query: str,
    records: list[ChunkRecord],
    reranker,
) -> list[tuple[ChunkRecord, float]]:
    if not records:
        return []
    scorer = reranker if reranker is not None else _default_reranker()
    texts = [record.content for record in records]
    scores = [float(value) for value in scorer.score(query, texts)]
    if len(scores) != len(records):
        raise RetrievalError("Reranker score count does not match chunk count")
    paired = list(zip(records, scores, strict=True))
    paired.sort(key=lambda item: item[1], reverse=True)
    return paired


def _default_reranker():
    from app.services.retrieval.reranker import get_reranker

    return get_reranker()


__all__ = [
    "DENSE_TOP_K",
    "NO_CONTEXT_ANSWER",
    "RERANK_TOP_K",
    "RRF_K",
    "RRF_TOP_K",
    "SNIPPET_LEN",
    "SPARSE_TOP_K",
    "ChunkRecord",
    "HybridPool",
    "RetrievalError",
    "RetrievalResult",
    "RetrievedChunk",
    "StageHit",
    "allowed_roles_for",
    "bm25_scores",
    "dense_search",
    "embed_query",
    "finish_retrieval",
    "hybrid_search",
    "reciprocal_rank_fusion",
    "retrieve",
    "sparse_search",
]
