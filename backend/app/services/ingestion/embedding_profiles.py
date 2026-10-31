"""Versioned embedding/reranker candidates used by isolated RAG evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingProfile:
    key: str
    model_name: str
    vector_size: int
    max_input_tokens: int
    metadata_token_reserve: int
    eval_chunk_max_tokens: int
    eval_chunk_min_tokens: int
    eval_chunk_overlap_tokens: int
    cache_markers: tuple[str, ...]
    estimated_size_gb: float


@dataclass(frozen=True)
class RerankerProfile:
    model_name: str
    cache_markers: tuple[str, ...]
    estimated_size_gb: float


_EMBEDDING_PROFILES = {
    "current": EmbeddingProfile(
        key="current",
        model_name="BAAI/bge-small-en-v1.5",
        vector_size=384,
        max_input_tokens=512,
        metadata_token_reserve=0,
        eval_chunk_max_tokens=600,
        eval_chunk_min_tokens=400,
        eval_chunk_overlap_tokens=50,
        cache_markers=("bge-small-en-v1.5",),
        estimated_size_gb=0.067,
    ),
    "multilingual-compact": EmbeddingProfile(
        key="multilingual-compact",
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        vector_size=384,
        max_input_tokens=128,
        metadata_token_reserve=32,
        eval_chunk_max_tokens=80,
        eval_chunk_min_tokens=48,
        eval_chunk_overlap_tokens=8,
        cache_markers=("paraphrase-multilingual-minilm-l12-v2",),
        estimated_size_gb=0.22,
    ),
}

_RERANKER_PROFILES = {
    "current": RerankerProfile(
        model_name="BAAI/bge-reranker-base",
        cache_markers=("bge-reranker-base",),
        estimated_size_gb=1.04,
    ),
    "multilingual-compact": RerankerProfile(
        model_name="BAAI/bge-reranker-v2-m3-int8",
        cache_markers=("model_int8",),
        estimated_size_gb=0.57,
    ),
}


def supported_profiles() -> tuple[str, ...]:
    return tuple(_EMBEDDING_PROFILES)


def embedding_profile(key: str) -> EmbeddingProfile:
    try:
        return _EMBEDDING_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown embedding profile: {key}") from exc


def reranker_profile(key: str) -> RerankerProfile:
    try:
        return _RERANKER_PROFILES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown reranker profile: {key}") from exc
