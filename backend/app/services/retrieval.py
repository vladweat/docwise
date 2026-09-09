"""Corpus hybrid retrieval with SQL RBAC.

Dense pgvector + BM25 on those candidates (ADR-005, until a sparse FTS index exists),
RRF k=60, then cross-encoder rerank. Never scrolls the chunk table into RAM.
ChainWise contract-audit branches are not ported.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Hashable, TypeVar
from uuid import UUID

from sqlalchemy import String, cast
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.models.user import User
from app.services.embeddings import embed_texts

logger = logging.getLogger(__name__)

DENSE_TOP_K = 25
SPARSE_TOP_K = 25
DENSE_CANDIDATE_LIMIT = 50
RRF_TOP_K = 15
RERANK_TOP_K = 4
RRF_K = 60
SNIPPET_LEN = 240
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[^\W\d_]+", re.UNICODE)

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


def allowed_roles_for(user: User) -> list[str]:
    """`{role} ∪ departments ∪ {all}`. Never read roles from a request body."""
    return list(user.allowed_roles())


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def bm25_scores(
    query: str,
    documents: list[str],
    *,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[float]:
    tokenized = [tokenize(doc) for doc in documents]
    query_tokens = tokenize(query)
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


def _roles_overlap(chunk_roles: list[str] | None, allowed_roles: list[str]) -> bool:
    return bool(set(chunk_roles or []) & set(allowed_roles))


def _stage_hit(row: DocumentChunk, score: float) -> StageHit:
    return StageHit(
        chunk_id=row.chunk_id,
        document_id=row.document_id,
        page=row.page_number,
        score=score,
        snippet=_snippet(row.content),
    )


def _snippet(content: str, max_len: int = SNIPPET_LEN) -> str:
    text = " ".join((content or "").split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _retrieved(row: DocumentChunk, score: float, dense_distance: float | None) -> RetrievedChunk:
    return RetrievedChunk(
        id=row.id,
        document_id=row.document_id,
        chunk_id=row.chunk_id,
        doc_title=row.doc_title or "",
        page_number=row.page_number,
        content=row.content,
        access_roles=tuple(row.access_roles or ()),
        score=score,
        section_title=row.section_title,
        is_table=bool(row.is_table),
        dense_distance=dense_distance,
    )


def dense_search(
    db: Session,
    query_vector: list[float],
    allowed_roles: list[str],
    *,
    limit: int = DENSE_CANDIDATE_LIMIT,
) -> list[tuple[DocumentChunk, float]]:
    """Cosine Top-N with `access_roles && allowed_roles`. Does not load the corpus."""
    if not query_vector or limit <= 0:
        return []
    distance = DocumentChunk.embedding.cosine_distance(query_vector)
    rows = (
        db.query(DocumentChunk, distance.label("distance"))
        .join(Document, Document.id == DocumentChunk.document_id)
        .filter(Document.status == DocumentStatus.ready.value)
        .filter(chunk_acl_filter(allowed_roles))
        .filter(DocumentChunk.embedding.isnot(None))
        .order_by(distance)
        .limit(limit)
        .all()
    )
    return [(chunk, float(dist)) for chunk, dist in rows]


def _sparse_ranking(query: str, candidates: list[DocumentChunk]) -> list[UUID]:
    if not candidates:
        return []
    scores = bm25_scores(query, [chunk.content for chunk in candidates])
    ranked = sorted(
        range(len(candidates)),
        key=lambda index: scores[index],
        reverse=True,
    )
    hits: list[UUID] = []
    for index in ranked:
        if scores[index] <= 0:
            continue
        hits.append(candidates[index].id)
        if len(hits) >= SPARSE_TOP_K:
            break
    return hits


def retrieve(
    db: Session,
    user: User,
    query: str,
    *,
    embedder=None,
    reranker=None,
) -> RetrievalResult:
    """Hybrid search for the authenticated user. Roles come from `user`, not the body."""
    allowed = allowed_roles_for(user)
    blank = RetrievalResult(chunks=[], allowed_roles=tuple(allowed))
    if not (query or "").strip():
        return blank

    try:
        vectors = embed_texts([query.strip()], embedder=embedder)
    except Exception as exc:
        raise RetrievalError(f"Query embedding failed: {exc}") from exc
    if not vectors:
        return blank

    candidates = dense_search(db, vectors[0], allowed)
    visible = [
        (chunk, dist)
        for chunk, dist in candidates
        if _roles_overlap(chunk.access_roles, allowed)
    ]
    if not visible:
        logger.info("retrieval empty after ACL dense search")
        return blank

    by_id = {chunk.id: (chunk, dist) for chunk, dist in visible}
    ordered = [chunk for chunk, _dist in visible]
    dense_ids = [chunk.id for chunk in ordered[:DENSE_TOP_K]]
    sparse_ids = _sparse_ranking(query, ordered)

    lists: list[list[UUID]] = [dense_ids]
    if sparse_ids:
        lists.append(sparse_ids)
    fused = reciprocal_rank_fusion(lists, k=RRF_K)[:RRF_TOP_K]

    dense_hits = [
        _stage_hit(chunk, 1.0 - dist if dist <= 1.0 else 0.0)
        for chunk, dist in visible[:DENSE_TOP_K]
    ]
    sparse_hits = [_stage_hit(by_id[cid][0], 1.0 / (1 + rank)) for rank, cid in enumerate(sparse_ids)]
    rrf_hits = [_stage_hit(by_id[cid][0], score) for cid, score in fused if cid in by_id]

    rrf_chunks = [by_id[cid][0] for cid, _score in fused if cid in by_id]
    scored = _rerank_chunks(query, rrf_chunks, reranker)
    threshold = get_settings().rerank_threshold
    kept = [(chunk, score) for chunk, score in scored if score >= threshold][:RERANK_TOP_K]

    reranked_hits = [_stage_hit(chunk, score) for chunk, score in kept]
    result_chunks = [
        _retrieved(chunk, score, by_id[chunk.id][1]) for chunk, score in kept
    ]
    if not result_chunks:
        logger.info("retrieval refuse: empty after rerank threshold=%.3f", threshold)
        return RetrievalResult(
            chunks=[],
            dense=dense_hits,
            sparse=sparse_hits,
            rrf=rrf_hits,
            reranked=[],
            allowed_roles=tuple(allowed),
        )

    return RetrievalResult(
        chunks=result_chunks,
        dense=dense_hits,
        sparse=sparse_hits,
        rrf=rrf_hits,
        reranked=reranked_hits,
        allowed_roles=tuple(allowed),
    )


def _rerank_chunks(
    query: str,
    chunks: list[DocumentChunk],
    reranker,
) -> list[tuple[DocumentChunk, float]]:
    if not chunks:
        return []
    scorer = reranker if reranker is not None else _default_reranker()
    texts = [chunk.content for chunk in chunks]
    scores = [float(value) for value in scorer.score(query, texts)]
    if len(scores) != len(chunks):
        raise RetrievalError("Reranker score count does not match chunk count")
    paired = list(zip(chunks, scores, strict=True))
    paired.sort(key=lambda item: item[1], reverse=True)
    return paired


def _default_reranker():
    from app.services.reranker import get_reranker

    return get_reranker()
