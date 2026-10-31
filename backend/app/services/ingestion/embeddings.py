"""Dense embeddings via FastEmbed `BAAI/bge-small-en-v1.5` (384d cosine).

Port of ChainWise `_FastEmbedEncoder` / `encode_texts` from `qdrant_indexer.py`,
without Qdrant. Vectors are written to `document_chunks.embedding`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.models.document import EMBEDDING_DIM
from app.services.ingestion.embedding_profiles import EmbeddingProfile, embedding_profile
from app.services.ingestion.onnx_cache import has_cached_onnx

logger = logging.getLogger(__name__)

MODEL_NAME = embedding_profile("current").model_name
VECTOR_SIZE = EMBEDDING_DIM

_embedder = None
_profile_key = "current"
_profile_embedders: dict[str, Any] = {}


class EmbeddingError(Exception):
    """Raised when the ONNX model is missing or a vector has the wrong size."""


def embedding_model_dir() -> Path:
    settings = get_settings()
    if settings.embedding_model_path:
        return Path(settings.embedding_model_path)
    return Path(__file__).resolve().parents[2] / ".models"


def is_embedder_available(profile_key: str | None = None) -> bool:
    profile = embedding_profile(profile_key) if profile_key else active_embedding_profile()
    return has_cached_onnx(embedding_model_dir(), *profile.cache_markers)


def active_embedding_profile() -> EmbeddingProfile:
    return embedding_profile(_profile_key)


def select_evaluation_embedding_profile(key: str) -> None:
    """Select a model only for the current eval process; normal app default stays fixed."""
    global _profile_key
    selected = embedding_profile(key)
    if key != "current" and get_settings().environment.strip().lower() == "production":
        raise RuntimeError("Evaluation embedding profiles are disabled in production")
    _profile_key = selected.key
    reset_embedder_cache()


def reset_embedder_cache() -> None:
    global _embedder, _profile_embedders
    _embedder = None
    _profile_embedders = {}


class FastEmbedEncoder:
    """Adapt fastembed.TextEmbedding to the encode() interface used in tests."""

    def __init__(self, model):
        self._model = model

    def encode(self, texts, **_kwargs):
        return list(self._model.embed(list(texts)))


def encode_texts(embedder, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    raw = embedder.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )
    if hasattr(raw, "tolist"):
        raw = raw.tolist()
    vectors: list[list[float]] = []
    for item in raw:
        vector = item.tolist() if hasattr(item, "tolist") else [float(value) for value in item]
        if len(vector) != VECTOR_SIZE:
            raise EmbeddingError(f"Expected {VECTOR_SIZE}-dim embeddings, got {len(vector)}")
        vectors.append(vector)
    if len(vectors) != len(texts):
        raise EmbeddingError("Embedding count does not match text count")
    return vectors


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = _load_embedder()
    return _embedder


def get_embedder_for_profile(profile_key: str):
    """Load an explicitly named encoder without changing the active RAG profile."""
    if profile_key == _profile_key:
        return get_embedder()
    if get_settings().environment.strip().lower() == "production":
        raise RuntimeError("Alternate embedding profiles are disabled in production")
    if profile_key not in _profile_embedders:
        _profile_embedders[profile_key] = _load_embedder(profile_key)
    return _profile_embedders[profile_key]


def embed_texts(texts: list[str], *, embedder=None) -> list[list[float]]:
    encoder = embedder if embedder is not None else get_embedder()
    return encode_texts(encoder, texts)


def embed_texts_for_profile(texts: list[str], profile_key: str) -> list[list[float]]:
    return encode_texts(get_embedder_for_profile(profile_key), texts)


def _load_embedder(profile_key: str | None = None):
    cache_dir = embedding_model_dir()
    profile = embedding_profile(profile_key) if profile_key else active_embedding_profile()
    if not is_embedder_available(profile.key):
        raise EmbeddingError(f"Embedding profile {profile.key} is not cached at {cache_dir}")
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbeddingError("fastembed is not installed") from exc

    logger.info("Loading %s from %s", profile.model_name, cache_dir)
    try:
        model = TextEmbedding(model_name=profile.model_name, cache_dir=str(cache_dir), local_files_only=True)
    except TypeError:
        model = TextEmbedding(model_name=profile.model_name, cache_dir=str(cache_dir))
    return FastEmbedEncoder(model)
