"""FastEmbed embedding shape and ONNX cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.document import EMBEDDING_DIM
from app.services.ingestion.embeddings import (
    MODEL_NAME,
    VECTOR_SIZE,
    EmbeddingError,
    encode_texts,
    embedding_model_dir,
    is_embedder_available,
    reset_embedder_cache,
)


class FakeEmbedder:
    def __init__(self, dim: int = VECTOR_SIZE):
        self.dim = dim
        self.texts: list[str] = []

    def encode(self, texts, **_kwargs):
        self.texts = list(texts)
        return [
            [float((index + offset) % 7) for offset in range(self.dim)]
            for index in range(len(texts))
        ]


def test_model_is_bge_small_384():
    assert MODEL_NAME == "BAAI/bge-small-en-v1.5"
    assert VECTOR_SIZE == 384
    assert VECTOR_SIZE == EMBEDDING_DIM


def test_encode_texts_returns_384d_vectors():
    embedder = FakeEmbedder()
    vectors = encode_texts(embedder, ["hello", "world"])
    assert embedder.texts == ["hello", "world"]
    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)
    assert vectors[0] != vectors[1]


def test_encode_texts_empty():
    assert encode_texts(FakeEmbedder(), []) == []


def test_encode_texts_rejects_wrong_size():
    with pytest.raises(EmbeddingError, match="384"):
        encode_texts(FakeEmbedder(dim=8), ["hello"])


def test_encode_texts_accepts_numpy_like():
    class Row:
        def __init__(self, values):
            self._values = values

        def tolist(self):
            return list(self._values)

    class Matrix:
        def __init__(self, rows):
            self._rows = rows

        def tolist(self):
            return self._rows

    class Numpyish:
        def encode(self, texts, **_kwargs):
            return Matrix([Row([0.0] * VECTOR_SIZE) for _ in texts])

    vectors = encode_texts(Numpyish(), ["a"])
    assert vectors == [[0.0] * VECTOR_SIZE]


def test_embedding_model_dir_uses_settings(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("EMBEDDING_MODEL_PATH", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_embedder_cache()
    assert embedding_model_dir() == tmp_path
    assert is_embedder_available() is False
    (tmp_path / "models--qdrant--bge-small-en-v1.5-onnx-q").mkdir()
    (tmp_path / "models--qdrant--bge-small-en-v1.5-onnx-q" / "model_optimized.onnx").write_bytes(b"onnx")
    assert is_embedder_available() is True
    get_settings.cache_clear()
    reset_embedder_cache()


def test_has_cached_onnx_matches_fastembed_hf_layout(monkeypatch, tmp_path: Path):
    from app.services.ingestion.onnx_cache import has_cached_onnx
    from app.services.retrieval.reranker import is_reranker_available, reset_reranker_cache

    embed_dir = tmp_path / "models--qdrant--bge-small-en-v1.5-onnx-q" / "snapshots" / "abc"
    embed_dir.mkdir(parents=True)
    (embed_dir / "model_optimized.onnx").write_bytes(b"onnx")
    assert has_cached_onnx(tmp_path, "bge-small") is True
    assert has_cached_onnx(tmp_path, "bge-reranker", "reranker-base") is False

    rerank_dir = tmp_path / "models--BAAI--bge-reranker-base" / "snapshots" / "def"
    rerank_dir.mkdir(parents=True)
    (rerank_dir / "model.onnx").write_bytes(b"onnx")
    assert has_cached_onnx(tmp_path, "bge-reranker", "reranker-base") is True

    monkeypatch.setenv("EMBEDDING_MODEL_PATH", str(tmp_path))
    from app.core.config import get_settings

    get_settings.cache_clear()
    reset_reranker_cache()
    assert is_reranker_available() is True
    get_settings.cache_clear()
    reset_reranker_cache()
