"""Corpus hybrid retrieval with SQL RBAC.

Dense pgvector Top-25 + independent Postgres FTS Top-25 (ADR-005), both with
`organization_id` and `access_roles && allowed_roles`, then RRF k=60 and
cross-encoder rerank. Never scrolls the chunk table into RAM.
ChainWise contract-audit branches are not ported.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Hashable, TypeVar
from uuid import UUID

from sqlalchemy import String, cast, func, literal_column, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.embeddings import embed_texts
from app.services.text import lexical_tokens

logger = logging.getLogger(__name__)

DENSE_TOP_K = 25
SPARSE_TOP_K = 25
RRF_TOP_K = 15
RERANK_TOP_K = 4
RRF_K = 60
SNIPPET_LEN = 240
TS_CONFIG = literal_column("'simple'::regconfig")

NO_CONTEXT_ANSWER = (
    "В предоставленных документах нет информации по данному вопросу."
)

T = TypeVar("T", bound=Hashable)


class RetrievalError(Exception):
    """Raised when query embedding or rerank fails."""


@dataclass(frozen=True)
class RetrievedChunk:
    id: UUID
    document_id: UUID
    chunk_id: str
    doc_title: str
    page_number: int
    content: str
    access_roles: tuple[str, ...]
    score: float
    section_title: str | None = None
    is_table: bool = False
    dense_distance: float | None = None

    def snippet(self, max_len: int = SNIPPET_LEN) -> str:
        text = " ".join(self.content.split())
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"

    def to_citation(self) -> dict[str, object]:
        return {
            "doc_id": str(self.document_id),
            "doc_title": self.doc_title,
            "page": self.page_number,
            "snippet": self.snippet(),
        }


@dataclass(frozen=True)
class StageHit:
    chunk_id: str
    document_id: UUID
    page: int
    score: float
    snippet: str


@dataclass(frozen=True)
class ChunkRecord:
    """Detached chunk fields so rerank/citations do not need an open Session."""

    id: UUID
    document_id: UUID
    chunk_id: str
    doc_title: str
    page_number: int
    content: str
    access_roles: tuple[str, ...]
    section_title: str | None = None
    is_table: bool = False
    dense_distance: float | None = None


@dataclass
class HybridPool:
    records: dict[UUID, ChunkRecord] = field(default_factory=dict)
    dense_ids: list[UUID] = field(default_factory=list)
    sparse_ids: list[UUID] = field(default_factory=list)
    fused: list[tuple[UUID, float]] = field(default_factory=list)
    dense: list[StageHit] = field(default_factory=list)
    sparse: list[StageHit] = field(default_factory=list)
    rrf: list[StageHit] = field(default_factory=list)
    allowed_roles: tuple[str, ...] = ()


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]
    dense: list[StageHit] = field(default_factory=list)
    sparse: list[StageHit] = field(default_factory=list)
    rrf: list[StageHit] = field(default_factory=list)
    reranked: list[StageHit] = field(default_factory=list)
    allowed_roles: tuple[str, ...] = ()

    @property
    def should_generate(self) -> bool:
        return bool(self.chunks)

    @property
    def refusal_text(self) -> str | None:
        if self.should_generate:
            return None
        return NO_CONTEXT_ANSWER


def allowed_roles_for(user) -> list[str]:
    """`{role} ∪ departments ∪ {all}` of the current membership. Never from a request body."""
    return list(user.allowed_roles())


def bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    """Okapi BM25 over in-memory strings (unit tests / ChainWise formula).

    Production sparse retrieval is Postgres FTS (`sparse_search`), not this function.
    """
    tokenized = [lexical_tokens(doc) for doc in documents]
    query_tokens = lexical_tokens(query)
    n_docs = len(documents)
    if n_docs == 0:
        return []
    avgdl = sum(len(doc) for doc in tokenized) / n_docs
    df: dict[str, int] = {}
    for doc in tokenized:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1

    scores: list[float] = []
    for doc in tokenized:
        tf: dict[str, int] = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        dl = len(doc) or 1
        score = 0.0
        for term in query_tokens:
            n_q = df.get(term, 0)
            if n_q == 0:
                continue
            idf = math.log(1 + (n_docs - n_q + 0.5) / (n_q + 0.5))
            freq = tf.get(term, 0)
            denom = freq + k1 * (1 - b + b * dl / avgdl)
            score += idf * (freq * (k1 + 1)) / denom
        scores.append(score)
    return scores


def reciprocal_rank_fusion(
    ranked_lists: list[list[T]],
    *,
    k: int = RRF_K,
) -> list[tuple[T, float]]:
    scores: dict[T, float] = {}
    for ranking in ranked_lists:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def chunk_acl_filter(allowed_roles: list[str]):
    return DocumentChunk.access_roles.overlap(cast(list(allowed_roles), ARRAY(String)))


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


def _corpus_query(db: Session, allowed_roles: list[str], organization_id: UUID):
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


def embed_query(query: str, *, embedder=None) -> list[float]:
    """FastEmbed of the question. Must not run while a DB session is held."""
    try:
        vectors = embed_texts([query.strip()], embedder=embedder)
    except Exception as exc:
        raise RetrievalError(f"Query embedding failed: {exc}") from exc
    if not vectors:
        raise RetrievalError("Query embedding returned no vector")
    return vectors[0]


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
        reranked=[],
        allowed_roles=allowed,
    )
    fused_records = [pool.records[cid] for cid, _score in pool.fused if cid in pool.records]
    if not fused_records:
        return blank

    scored = _rerank_records(query, fused_records, reranker)
    threshold = get_settings().rerank_threshold
    kept = [(record, score) for record, score in scored if score >= threshold][:RERANK_TOP_K]
    if not kept:
        logger.info("retrieval refuse: empty after rerank threshold=%.3f", threshold)
        return blank

    reranked_hits = [_stage_hit(record, score) for record, score in kept]
    result_chunks = [_retrieved(record, score) for record, score in kept]
    return RetrievalResult(
        chunks=result_chunks,
        dense=list(pool.dense),
        sparse=list(pool.sparse),
        rrf=list(pool.rrf),
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
    from app.services.reranker import get_reranker

    return get_reranker()
