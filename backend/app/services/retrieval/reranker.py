"""Cross-encoder rerank via FastEmbed `BAAI/bge-reranker-base`.

Scores are sigmoid-mapped to (0, 1) so the 0.25 threshold in the spec is a
unit-interval cutoff, not a raw logit.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path

from app.core.config import get_settings
from app.services.ingestion.embedding_profiles import RerankerProfile, reranker_profile
from app.services.ingestion.onnx_cache import has_cached_onnx

logger = logging.getLogger(__name__)

MODEL_NAME = reranker_profile("current").model_name

_reranker = None
_profile_key = "current"


class RerankError(Exception):
    """Raised when the ONNX reranker is missing or scoring fails."""


def reranker_model_dir() -> Path:
    settings = get_settings()
    if settings.embedding_model_path:
        return Path(settings.embedding_model_path)
    return Path(__file__).resolve().parents[2] / ".models"


def is_reranker_available() -> bool:
    return has_cached_onnx(reranker_model_dir(), *active_reranker_profile().cache_markers)


def active_reranker_profile() -> RerankerProfile:
    return reranker_profile(_profile_key)


def select_evaluation_reranker_profile(key: str) -> None:
    """Select a model only for the current eval process; normal app default stays fixed."""
    global _profile_key
    reranker_profile(key)
    if key != "current" and get_settings().environment.strip().lower() == "production":
        raise RuntimeError("Evaluation reranker profiles are disabled in production")
    _profile_key = key
    reset_reranker_cache()


def reset_reranker_cache() -> None:
    global _reranker
    _reranker = None


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1.0 + exp)


class FastEmbedReranker:
    def __init__(self, model):
        self._model = model

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        raw = list(self._model.rerank(query, documents))
        if len(raw) != len(documents):
            raise RerankError("Reranker returned the wrong number of scores")
        return [_sigmoid(float(value)) for value in raw]


def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = _load_reranker()
    return _reranker


def _load_reranker():
    cache_dir = reranker_model_dir()
    profile = active_reranker_profile()
    if not is_reranker_available():
        raise RerankError(f"Reranker profile {profile.model_name} is not cached at {cache_dir}")
    try:
        from fastembed.rerank.cross_encoder import TextCrossEncoder
    except ImportError as exc:
        raise RerankError("fastembed is not installed") from exc

    logger.info("Loading %s from %s", profile.model_name, cache_dir)
    kwargs = {"model_name": profile.model_name, "cache_dir": str(cache_dir)}
    try:
        model = TextCrossEncoder(**kwargs, local_files_only=True)
    except TypeError:
        model = TextCrossEncoder(**kwargs)
    return FastEmbedReranker(model)
