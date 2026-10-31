"""Small, deterministic checks for multilingual eval profiles and citation scoring."""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.services.ingestion.embedding_profiles import embedding_profile, reranker_profile
from app.services.ingestion import embeddings
from app.services.retrieval import reranker


def _eval_module(name: str):
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "eval" / f"{name}.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"eval_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_multilingual_profile_fits_existing_vector_dimension_and_chunk_budget():
    profile = embedding_profile("multilingual-compact")

    assert profile.vector_size == 384
    assert profile.max_input_tokens == 128
    assert profile.eval_chunk_max_tokens + profile.metadata_token_reserve <= profile.max_input_tokens


def test_unknown_embedding_profile_is_rejected_without_fallback():
    with pytest.raises(ValueError, match="Unknown embedding profile"):
        embedding_profile("invented-model")


def test_multilingual_reranker_uses_resource_bounded_int8_profile():
    profile = reranker_profile("multilingual-compact")

    assert profile.model_name == "BAAI/bge-reranker-v2-m3-int8"
    assert profile.estimated_size_gb < reranker_profile("current").estimated_size_gb


def test_eval_profile_selection_is_explicit_and_can_be_reset(monkeypatch):
    monkeypatch.setattr(embeddings, "get_settings", lambda: SimpleNamespace(environment="test"))
    monkeypatch.setattr(reranker, "get_settings", lambda: SimpleNamespace(environment="test"))
    assert embeddings.active_embedding_profile().key == "current"

    embeddings.select_evaluation_embedding_profile("multilingual-compact")
    assert embeddings.active_embedding_profile().model_name == (
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    embeddings.select_evaluation_embedding_profile("current")
    assert embeddings.active_embedding_profile().key == "current"

    reranker.select_evaluation_reranker_profile("multilingual-compact")
    assert reranker.active_reranker_profile().model_name == "BAAI/bge-reranker-v2-m3-int8"
    reranker.select_evaluation_reranker_profile("current")


def test_eval_profiles_cannot_be_selected_in_production(monkeypatch):
    monkeypatch.setattr(embeddings, "get_settings", lambda: SimpleNamespace(environment="production"))
    monkeypatch.setattr(reranker, "get_settings", lambda: SimpleNamespace(environment="production"))

    with pytest.raises(RuntimeError, match="disabled in production"):
        embeddings.select_evaluation_embedding_profile("multilingual-compact")
    with pytest.raises(RuntimeError, match="disabled in production"):
        reranker.select_evaluation_reranker_profile("multilingual-compact")


def test_citation_support_rate_counts_only_claims_with_valid_source_indexes():
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {"claims": [
            {"claim": "A supported claim", "source_indexes": [0]},
            {"claim": "An unsupported claim", "source_indexes": []},
            {"claim": "An invalid source", "source_indexes": [8]},
        ]},
        source_count=2,
    )

    assert score == pytest.approx(1 / 3)


def test_citation_support_recognizes_a_verbatim_claim_when_judge_omits_its_source():
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {"claims": [{
            "claim": "The default Python version for engineering services is 3.12.",
            "source_indexes": [],
        }]},
        source_count=1,
        sources=["Toolchain: The default Python version for engineering services is 3.12."],
    )

    assert score == 1.0


def test_citation_support_recognizes_a_near_verbatim_claim_with_one_omitted_source_word():
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {"claims": [{
            "claim": "The default Python version for engineering is 3.12.",
            "source_indexes": [],
        }]},
        source_count=1,
        sources=["The default Python version for engineering services is 3.12."],
    )

    assert score == 1.0


def test_citation_support_does_not_treat_a_conflicting_verbatim_claim_as_supported():
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {"claims": [{"claim": "The default Python version is 3.11.", "source_indexes": []}]},
        source_count=1,
        sources=["The default Python version is 3.12."],
    )

    assert score == 0.0


def test_citation_support_is_unavailable_for_answers_without_factual_claims():
    metrics = _eval_module("citation_metrics")

    assert metrics.citation_support_rate({"claims": []}, source_count=3) is None


def test_citation_support_rejects_malformed_claim_payload():
    metrics = _eval_module("citation_metrics")

    with pytest.raises(metrics.CitationJudgeError):
        metrics.citation_support_rate({"claims": [{"claim": "Claim", "source_indexes": "0"}]}, source_count=1)


def test_citation_judge_scores_answer_claims_against_numbered_sources(monkeypatch):
    metrics = _eval_module("metrics")
    captured = []
    monkeypatch.setattr(
        metrics,
        "_complete_json",
        lambda messages: captured.append(messages) or {
            "claims": [
                {"claim": "A fact", "source_indexes": [0]},
                {"claim": "An unsupported fact", "source_indexes": []},
            ]
        },
    )

    score = metrics._citation_support("Question", "Answer", ["First source", "Second source"])

    assert score == pytest.approx(0.5)
    prompt = captured[0][1]["content"]
    assert "[0] First source" in prompt and "[1] Second source" in prompt


def test_citation_judge_skips_refusals_and_empty_sources():
    metrics = _eval_module("metrics")

    assert metrics._citation_support("Q", metrics.NO_CONTEXT_ANSWER, ["source"]) is None
    assert metrics._citation_support("Q", "An answer", []) is None


def test_answer_relevance_uses_a_fixed_encoder_by_question_language(monkeypatch):
    metrics = _eval_module("metrics")
    captured = []
    monkeypatch.setattr(
        metrics,
        "embed_texts_for_profile",
        lambda texts, key: captured.append(key) or [[1.0]] * len(texts),
    )
    monkeypatch.setattr(metrics, "_complete_json", lambda _messages: {"questions": ["One", "Two"]})

    metrics._answer_relevance("What is the policy?", "A policy answer.")
    metrics._answer_relevance("Какова политика?", "Ответ о политике.")

    assert captured == ["current", "multilingual-compact"]
