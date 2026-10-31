"""SQL dense/sparse retrieval and hybrid pool assembly (session required)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, literal_column, text
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.config import get_settings
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.retrieval.types import (
    DENSE_TOP_K,
    RRF_K,
    RRF_TOP_K,
    SNIPPET_LEN,
    SPARSE_TOP_K,
    ChunkRecord,
    HybridPool,
    StageHit,
    allowed_roles_for,
    chunk_acl_filter,
    reciprocal_rank_fusion,
)
from app.services.text import lexical_tokens

logger = logging.getLogger(__name__)

TS_CONFIG: ColumnElement = literal_column("'simple'::regconfig")

_FTS_STOP = {
    "a",
    "an",
    "and",
    "are",
    "be",
    "can",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "must",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "which",
    "who",
    "with",
    "где",
    "для",
    "или",
    "из",
    "как",
    "на",
    "не",
    "по",
    "что",
    "это",
}


def _roles_overlap(chunk_roles: list[str] | tuple[str, ...] | None, allowed_roles: list[str]) -> bool:
    return bool(set(chunk_roles or []) & set(allowed_roles))


def _snippet(content: str, max_len: int = SNIPPET_LEN) -> str:
    text = " ".join((content or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _stage_hit(record: ChunkRecord, score: float) -> StageHit:
    return StageHit(
        chunk_id=record.chunk_id,
        document_id=record.document_id,
        page=record.page_number,
        score=score,
        snippet=_snippet(record.content),
        section_title=record.section_title,
    )


def _chunk_record(row: DocumentChunk, dense_distance: float | None = None) -> ChunkRecord:
    return ChunkRecord(
        id=row.id,
        document_id=row.document_id,
        chunk_id=row.chunk_id,
        doc_title=row.doc_title or "",
        page_number=row.page_number,
        content=row.content,
        access_roles=tuple(row.access_roles or ()),
        section_title=row.section_title,
        is_table=bool(row.is_table),
        dense_distance=dense_distance,
    )


def _corpus_query(db: Session, allowed_roles: list[str], organization_id: UUID):
    """Ready chunks in one org that pass inner ACL (dense, sparse, and hybrid must use this)."""
    return (
        db.query(DocumentChunk)
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(DocumentChunk.organization_id == organization_id)
        .filter(Document.organization_id == organization_id)
        .filter(Document.status == DocumentStatus.ready.value)
        .filter(chunk_acl_filter(allowed_roles))
    )


def _configure_filtered_hnsw(db: Session) -> None:
    """Ask pgvector to keep scanning the HNSW graph until the org/ACL filter is satisfied.

    The index is global; without iterative scan, `ORDER BY embedding <=> q LIMIT 25`
    can miss in-org neighbors that sit behind foreign-org closer vectors.
    """
    settings = get_settings()
    names = {
        row[0]
        for row in db.execute(text("SELECT name FROM pg_settings WHERE name LIKE 'hnsw.%'"))
    }
    mode = (settings.hnsw_iterative_scan or "relaxed_order").strip().lower()
    if mode not in {"off", "relaxed_order", "strict_order"}:
        mode = "relaxed_order"
    if "hnsw.iterative_scan" in names:
        db.execute(text(f"SET LOCAL hnsw.iterative_scan = '{mode}'"))
    if "hnsw.max_scan_tuples" in names:
        budget = max(int(settings.hnsw_max_scan_tuples), DENSE_TOP_K)
        db.execute(text(f"SET LOCAL hnsw.max_scan_tuples = {int(budget)}"))


def dense_search(
    db: Session,
    query_vector: list[float],
    allowed_roles: list[str],
    *,
    organization_id: UUID,
    limit: int = DENSE_TOP_K,
) -> list[tuple[DocumentChunk, float]]:
    """Cosine Top-N with org + `access_roles && allowed_roles`. Does not load the corpus."""
    if not query_vector or limit <= 0:
        return []
    _configure_filtered_hnsw(db)
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    rows = (
        _corpus_query(db, allowed_roles, organization_id)
        .add_columns(distance.label("distance"))
        .filter(DocumentChunk.embedding.isnot(None))
        .order_by(distance)
        .limit(limit)
        .all()
    )
    return [(chunk, float(dist)) for chunk, dist in rows]


def _fts_or_query(query: str) -> str | None:
    """OR-query from lexical tokens. `simple` has no stopwords; AND of the raw question would miss."""
    tokens = [token for token in lexical_tokens(query) if token not in _FTS_STOP and len(token) >= 2]
    if not tokens:
        tokens = [token for token in lexical_tokens(query) if len(token) >= 2]
    safe: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        if not token.replace("_", "").isalnum() and not token.isalpha():
            continue
        seen.add(token)
        safe.append(token)
        if len(safe) >= 32:
            break
    if not safe:
        return None
    return " | ".join(safe)


def sparse_search(
    db: Session,
    query: str,
    allowed_roles: list[str],
    *,
    organization_id: UUID,
    limit: int = SPARSE_TOP_K,
) -> list[tuple[DocumentChunk, float]]:
    """FTS Top-N independent of dense, same org + ACL. Does not load the corpus."""
    fts = _fts_or_query(query)
    if not fts or limit <= 0:
        return []
    tsquery = func.to_tsquery(TS_CONFIG, fts)
    rank = func.ts_rank_cd(DocumentChunk.search_vector, tsquery)
    rows = (
        _corpus_query(db, allowed_roles, organization_id)
        .add_columns(rank.label("rank"))
        .filter(DocumentChunk.search_vector.op("@@")(tsquery))
        .order_by(rank.desc(), DocumentChunk.id)
        .limit(limit)
        .all()
    )
    return [(chunk, float(score or 0.0)) for chunk, score in rows]


def hybrid_search(
    db: Session,
    user,
    query: str,
    query_vector: list[float],
) -> HybridPool:
    """SQL dense + FTS only. Copies rows into dataclasses before the caller closes the session."""
    allowed = allowed_roles_for(user)
    organization_id = user.organization_id
    pool = HybridPool(allowed_roles=tuple(allowed))
    if not (query or "").strip() or not query_vector:
        return pool

    dense_rows = dense_search(db, query_vector, allowed, organization_id=organization_id)
    sparse_rows = sparse_search(db, query, allowed, organization_id=organization_id)

    records: dict[UUID, ChunkRecord] = {}
    dense_ids: list[UUID] = []
    for chunk, dist in dense_rows:
        if not _roles_overlap(chunk.access_roles, allowed):
            continue
        records[chunk.id] = _chunk_record(chunk, dense_distance=float(dist))
        dense_ids.append(chunk.id)

    sparse_ids: list[UUID] = []
    sparse_scores: dict[UUID, float] = {}
    for chunk, score in sparse_rows:
        if not _roles_overlap(chunk.access_roles, allowed):
            continue
        if chunk.id not in records:
            records[chunk.id] = _chunk_record(chunk)
        sparse_ids.append(chunk.id)
        sparse_scores[chunk.id] = float(score)

    if not records:
        logger.info("retrieval empty after ACL dense+sparse search")
        return pool

    lists: list[list[UUID]] = []
    if dense_ids:
        lists.append(dense_ids)
    if sparse_ids:
        lists.append(sparse_ids)
    fused = reciprocal_rank_fusion(lists, k=RRF_K)[:RRF_TOP_K] if lists else []

    pool.records = records
    pool.dense_ids = dense_ids
    pool.sparse_ids = sparse_ids
    pool.fused = fused
    pool.dense = []
    for cid in dense_ids:
        record = records.get(cid)
        if record is None:
            continue
        dist = record.dense_distance or 0.0
        score = 1.0 - dist if dist <= 1.0 else 0.0
        pool.dense.append(_stage_hit(record, score))
    pool.sparse = [
        _stage_hit(records[cid], sparse_scores.get(cid, 0.0))
        for cid in sparse_ids
        if cid in records
    ]
    pool.rrf = [_stage_hit(records[cid], score) for cid, score in fused if cid in records]
    return pool
