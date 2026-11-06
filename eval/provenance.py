"""Reproducibility metadata for saved evaluation reports."""

from __future__ import annotations

import hashlib
import os
import subprocess
from collections.abc import Mapping
from pathlib import Path

UNAVAILABLE = "unavailable"
NOT_RUN = "not_run"
EVALUATION_FRAMEWORK = "Docwise in-repo Ragas-style evaluator"
EVALUATION_FRAMEWORK_VERSION = "not_applicable (versioned with the Git commit)"


def _repo_root(repo_root: Path | None = None) -> Path:
    return repo_root or Path(__file__).resolve().parent.parent


def code_revision(repo_root: Path | None = None) -> str:
    configured = os.environ.get("DOCWISE_GIT_REVISION", "").strip()
    if configured and configured.lower() not in {"unknown", "unrecorded", UNAVAILABLE}:
        return configured
    try:
        result = subprocess.run(
            ["git", "-C", str(_repo_root(repo_root)), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return UNAVAILABLE
    return result.stdout.strip() or UNAVAILABLE


def working_tree_dirty(repo_root: Path | None = None) -> bool | str:
    configured = os.environ.get("DOCWISE_GIT_DIRTY")
    if configured is not None:
        normalized = configured.strip().lower()
        if normalized in {"true", "1", "yes", "dirty"}:
            return True
        if normalized in {"false", "0", "no", "clean"}:
            return False
        return UNAVAILABLE
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(_repo_root(repo_root)),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return UNAVAILABLE
    return bool(result.stdout.strip())


def dataset_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluation_config(*, retrieval_only: bool = False) -> dict[str, str | int | float]:
    """Return safe runtime settings; never include credentials or service endpoints."""
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
    model = openai_model()
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
        "llm_model": model,
        "judge_model": NOT_RUN if retrieval_only else model,
        "dense_top_k": DENSE_TOP_K,
        "sparse_top_k": SPARSE_TOP_K,
        "rrf_top_k": RRF_TOP_K,
        "rrf_k": RRF_K,
        "rerank_top_k": RERANK_TOP_K,
        "rerank_threshold": float(settings.rerank_threshold),
        "hnsw_iterative_scan": settings.hnsw_iterative_scan or UNAVAILABLE,
        "hnsw_max_scan_tuples": int(settings.hnsw_max_scan_tuples),
        "generation_temperature": 0.2,
        "judge_temperature": 0.0,
        "system_prompt_sha256": prompt_hash,
    }


def capture_metadata(
    dataset_path: Path,
    *,
    evaluation_profile: str,
    timestamp: str,
    retrieval_only: bool,
    runtime_parameters: Mapping[str, str | int | float | bool] | None = None,
    configuration: Mapping[str, str | int | float] | None = None,
) -> dict[str, object]:
    config = configuration if configuration is not None else evaluation_config(retrieval_only=retrieval_only)
    runtime = runtime_parameters if runtime_parameters is not None else {}

    def config_value(key: str) -> object:
        return _available(config.get(key))

    def runtime_value(key: str) -> object:
        return _available(runtime.get(key))

    return {
        "schema_version": 1,
        "git_commit_sha": code_revision(),
        "working_tree_dirty": working_tree_dirty(),
        "dataset_sha256": dataset_sha256(dataset_path),
        "evaluation_profile": _available(evaluation_profile),
        "embedding_model_identifier": config_value("embedding_model"),
        "reranker_model_identifier": config_value("reranker_model"),
        "llm_model_identifier": NOT_RUN if retrieval_only else config_value("llm_model"),
        "judge_model_identifier": NOT_RUN if retrieval_only else config_value("judge_model"),
        "retrieval_parameters": {
            key: config_value(key)
            for key in (
                "dense_top_k",
                "sparse_top_k",
                "rrf_top_k",
                "rrf_k",
                "hnsw_iterative_scan",
                "hnsw_max_scan_tuples",
            )
        },
        "reranking_parameters": {
            "top_k": config_value("rerank_top_k"),
            "threshold": config_value("rerank_threshold"),
            "batch_size": runtime_value("rerank_batch_size"),
        },
        "runtime_parameters": {
            "concurrency": runtime_value("concurrency"),
            "embedding_batch_size": runtime_value("embedding_batch_size"),
            "limit": runtime_value("limit"),
            "retrieval_only": retrieval_only,
        },
        "timestamp": _available(timestamp),
        "evaluation_framework": EVALUATION_FRAMEWORK,
        "evaluation_framework_version": EVALUATION_FRAMEWORK_VERSION,
    }


def _available(value: object) -> object:
    return UNAVAILABLE if value is None or value == "" else value
