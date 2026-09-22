"""Retrieval datatypes, constants, and rank-fusion helpers (no DB I/O)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Hashable, TypeVar
from uuid import UUID

from sqlalchemy import String, cast
from sqlalchemy.dialects.postgresql import ARRAY

from app.models.document import DocumentChunk
from app.services.text import lexical_tokens

DENSE_TOP_K = 25
SPARSE_TOP_K = 25
RRF_TOP_K = 15
RERANK_TOP_K = 4
RRF_K = 60
SNIPPET_LEN = 240

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
        page = self.page_number if self.page_number > 0 else None
        section = (self.section_title or "").strip() or None
        if page is None and not section:
            section = "Document"
        return {
            "doc_id": str(self.document_id),
            "doc_title": self.doc_title,
            "page": page,
            "section": section,
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
    """Fuse dense and sparse rank lists with RRF (default k=60, ADR-005)."""
    scores: dict[T, float] = {}
    for ranking in ranked_lists:
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


def chunk_acl_filter(allowed_roles: list[str]):
    """SQL overlap predicate for retrieval; apply with organization_id on every search path."""
    return DocumentChunk.access_roles.overlap(cast(list(allowed_roles), ARRAY(String)))
