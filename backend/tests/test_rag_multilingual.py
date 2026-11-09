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


@pytest.mark.parametrize(
    ("claim", "source"),
    [
        (
            "Employees receive paid leave.",
            "Employees never receive paid leave.",
        ),
        (
            "Employees can receive benefits.",
            "Employees can't receive benefits.",
        ),
        (
            "Работник получает отпуск.",
            "Работник не получает отпуск.",
        ),
    ],
)
def test_citation_support_does_not_drop_negation_in_deterministic_fallback(claim, source):
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {"claims": [{"claim": claim, "source_indexes": []}]},
        source_count=1,
        sources=[source],
    )

    assert score == 0.0


def test_citation_support_allows_unrelated_negation_in_a_later_sentence():
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {"claims": [{"claim": "The allowance is 20 days.", "source_indexes": []}]},
        source_count=1,
        sources=["The allowance is 20 days. Sick leave is not specified here."],
    )

    assert score == 1.0


def test_offline_semantic_citation_cases_cover_paraphrase_quantity_and_polarity():
    metrics = _eval_module("citation_metrics")

    score = metrics.citation_support_rate(
        {
            "claims": [
                {"claim": "Employees may take 12 weeks of parental leave.", "source_indexes": [0]},
                {"claim": "Сотрудник получает оплачиваемый отпуск за выслугу лет.", "source_indexes": [1]},
                {"claim": "Employees may take 20 weeks of parental leave.", "source_indexes": []},
                {"claim": "Работник получает оплачиваемый отпуск.", "source_indexes": []},
            ]
        },
        source_count=2,
        sources=[
            "Eligible parents can take up to twelve weeks away from work after a child's birth.",
            "Работнику предоставляется оплачиваемый отпуск за выслугу лет.",
            "Работник не получает оплачиваемый отпуск.",
        ],
    )

    assert score == pytest.approx(0.5)


def test_citation_reference_precision_matches_retrieved_pdf_pages_and_docx_sections():
    metrics = _eval_module("citation_metrics")

    result = metrics.citation_reference_metrics(
        "The leave is paid [Policy.pdf, стр. 2]. See [Leave.docx, раздел: Annual leave]. "
        "The handbook says [Other.pdf, стр. 2] and [policy.pdf, стр. 2].",
        [
            {"doc_title": "Policy.pdf", "page": 2, "section": None},
            {"doc_title": "Leave.docx", "page": None, "section": "Annual leave"},
        ],
    )

    assert result.valid_references == 2
    assert result.total_references == 4
    assert result.precision == pytest.approx(0.5)


def test_citation_reference_precision_handles_brackets_in_source_title():
    metrics = _eval_module("citation_metrics")

    result = metrics.citation_reference_metrics(
        "See [Guide [HR].pdf, стр. 3].",
        [{"doc_title": "Guide [HR].pdf", "page": 3, "section": None}],
    )

    assert result.precision == 1.0


def test_citation_reference_precision_is_unavailable_when_answer_has_no_citations():
    metrics = _eval_module("citation_metrics")

    result = metrics.citation_reference_metrics(
        "The policy allows annual leave.",
        [{"doc_title": "Policy.pdf", "page": 2, "section": None}],
    )

    assert result.precision is None
    assert result.valid_references == 0
    assert result.total_references == 0


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
    system_prompt = captured[0][0]["content"]
    assert "[0] First source" in prompt and "[1] Second source" in prompt
    assert "negation" in system_prompt.lower()
    assert "quantities" in system_prompt.lower()


def test_score_case_reports_deterministic_citation_reference_precision(monkeypatch):
    metrics = _eval_module("metrics")
    monkeypatch.setattr(metrics, "_faithfulness", lambda *_args: 1.0)
    monkeypatch.setattr(metrics, "_context_relevance_flags", lambda *_args: [True])
    monkeypatch.setattr(metrics, "_citation_support", lambda *_args: 0.5)

    scores = metrics.score_case(
        question="What is the leave policy?",
        answer="See [Policy.pdf, стр. 2] and [Unknown.pdf, стр. 1].",
        contexts=["Employees get annual leave."],
        ground_truth="Employees get annual leave.",
        include_answer_relevance=False,
        citation_sources=[
            {"doc_title": "Policy.pdf", "page": 2, "section": None},
        ],
    )

    assert scores.citation_reference_precision == pytest.approx(0.5)
    assert scores.citation_reference_valid_count == 1
    assert scores.citation_reference_count == 2


def test_eval_runner_supplies_retrieved_source_metadata_to_citation_metrics(monkeypatch):
    run_eval = _eval_module("run_eval")
    citation = {"doc_id": "doc-1", "doc_title": "Policy.pdf", "page": 2, "section": None}
    captured = {}
    monkeypatch.setattr(run_eval, "_generate", lambda *_args: "A factual answer [Policy.pdf, стр. 2].")
    monkeypatch.setattr(
        run_eval,
        "score_case",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(relevance_questions=[]),
    )
    case = SimpleNamespace(
        question="What is the policy?",
        ground_truth_answer="The policy is documented.",
        is_no_answer=False,
        is_acl_negative=False,
    )
    result = SimpleNamespace(case=case, leaks=[], contexts=["Policy text."])
    chunk = SimpleNamespace(content="Policy text.", to_citation=lambda: citation)

    run_eval._evaluate_prepared_case(SimpleNamespace(result=result, chunks=[chunk]))

    assert captured["citation_sources"] == [citation]


def test_eval_runner_excludes_acl_leaked_sources_from_citation_validation(monkeypatch):
    run_eval = _eval_module("run_eval")
    captured = {}
    monkeypatch.setattr(run_eval, "_generate", lambda *_args: "No sources available.")
    monkeypatch.setattr(
        run_eval,
        "score_case",
        lambda **kwargs: captured.update(kwargs) or SimpleNamespace(relevance_questions=[]),
    )
    case = SimpleNamespace(
        question="What is the policy?",
        ground_truth_answer="The policy is documented.",
        is_no_answer=False,
        is_acl_negative=True,
    )
    result = SimpleNamespace(case=case, leaks=["restricted-doc"], contexts=["redacted"])
    chunk = SimpleNamespace(content="restricted text", to_citation=lambda: {"doc_title": "Secret.pdf"})

    run_eval._evaluate_prepared_case(SimpleNamespace(result=result, chunks=[chunk]))

    assert captured["contexts"] == []
    assert captured["citation_sources"] == []


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
