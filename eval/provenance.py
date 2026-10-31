"""Small, deterministic provenance fields for saved evaluation reports."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path


def code_revision() -> str:
    configured = os.environ.get("DOCWISE_GIT_REVISION", "").strip()
    if configured:
        return configured
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(Path(__file__).resolve().parent.parent),
                "rev-parse",
                "--short",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unrecorded"
    return result.stdout.strip() or "unrecorded"


def dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluation_config() -> dict[str, str | int | float]:
    """Return reproducibility metadata while excluding credentials and endpoints."""
    from app.core.config import get_settings
    from app.services.chat.llm import openai_model
    from app.services.chat.prompt import SYSTEM_PROMPT
    from app.services.ingestion.embeddings import active_embedding_profile
    from app.services.retrieval import (
        DENSE_TOP_K,
        RERANK_TOP_K,
        RRF_K,
        RRF_TOP_K,
        SPARSE_TOP_K,
    )
    from app.services.retrieval.reranker import active_reranker_profile

    settings = get_settings()
    embedding = active_embedding_profile()
    reranker = active_reranker_profile()
    prompt_hash = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    return {
        "embedding_model": embedding.model_name,
        "embedding_profile": embedding.key,
        "answer_relevance_encoders": (
            "Latin=BAAI/bge-small-en-v1.5; Cyrillic="
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        ),
        "embedding_max_input_tokens": embedding.max_input_tokens,
        "eval_chunk_max_tokens": embedding.eval_chunk_max_tokens,
        "reranker_model": reranker.model_name,
        "reranker_size_gb_estimate": reranker.estimated_size_gb,
        "llm_model": openai_model(),
        "dense_top_k": DENSE_TOP_K,
        "sparse_top_k": SPARSE_TOP_K,
        "rrf_top_k": RRF_TOP_K,
        "rrf_k": RRF_K,
        "rerank_top_k": RERANK_TOP_K,
        "rerank_threshold": float(settings.rerank_threshold),
        "system_prompt_sha256": prompt_hash,
    }
