"""Dense embeddings via FastEmbed `BAAI/bge-small-en-v1.5` (384d cosine).

Port of ChainWise `_FastEmbedEncoder` / `encode_texts` from `qdrant_indexer.py`,
without Qdrant. Vectors are written to `document_chunks.embedding`.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.models.document import EMBEDDING_DIM
from app.services.onnx_cache import has_cached_onnx

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = EMBEDDING_DIM

_embedder = None


class EmbeddingError(Exception):
    """Raised when the ONNX model is missing or a vector has the wrong size."""


def embedding_model_dir() -> Path:
    settings = get_settings()
    if settings.embedding_model_path:
        return Path(settings.embedding_model_path)
    return Path(__file__).resolve().parents[2] / ".models"


def is_embedder_available() -> bool:
    return has_cached_onnx(embedding_model_dir(), "bge-small")


def reset_embedder_cache() -> None:
    global _embedder
    _embedder = None


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


def embed_texts(texts: list[str], *, embedder=None) -> list[list[float]]:
    encoder = embedder if embedder is not None else get_embedder()
    return encode_texts(encoder, texts)


def _load_embedder():
    cache_dir = embedding_model_dir()
    if not is_embedder_available():
        raise EmbeddingError(f"Embedding model not found at {cache_dir}. Run: make embeddings")
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise EmbeddingError("fastembed is not installed") from exc

    logger.info("Loading %s from %s", MODEL_NAME, cache_dir)
    kwargs = {"model_name": MODEL_NAME, "cache_dir": str(cache_dir)}
    try:
        model = TextEmbedding(**kwargs, local_files_only=True)
    except TypeError:
        model = TextEmbedding(**kwargs)
    return FastEmbedEncoder(model)
