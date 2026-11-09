"""Deterministic report helpers and safe evaluation provenance."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest


def _eval_module(name: str):
    eval_dir = Path(__file__).resolve().parents[2] / "eval"
    if str(eval_dir) not in sys.path:
        sys.path.insert(0, str(eval_dir))
    spec = importlib.util.spec_from_file_location(f"eval_{name}", eval_dir / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_question_language_is_deterministic_for_script_types():
    reporting = _eval_module("reporting")

    assert reporting.question_language("What is our policy?") == "en"
    assert reporting.question_language("Какова политика компании?") == "ru"
    assert reporting.question_language("Какова policy компании?") == "mixed"
    assert reporting.question_language("123 — ?") == "unknown"


def test_rerank_threshold_sweep_simulates_filter_and_topk_from_one_score_list():
    reporting = _eval_module("reporting")
    hits = [
        SimpleNamespace(document_id="other", section_title="other", score=0.9),
        SimpleNamespace(document_id="target", section_title="target", score=0.22),
        SimpleNamespace(document_id="target", section_title="target", score=0.18),
    ]

    outcomes = reporting.rerank_threshold_case_metrics(
        hits,
        target_doc_id="target",
        target_section="target",
        thresholds=(0.15, 0.25),
        top_k=4,
    )

    assert outcomes["0.15"]["section_rank"] == 2
    assert outcomes["0.15"]["target_doc_hit"] is True
    assert outcomes["0.15"]["returned"] == 3
    assert outcomes["0.25"]["section_rank"] is None
    assert outcomes["0.25"]["target_doc_hit"] is False
    assert outcomes["0.25"]["returned"] == 1


@dataclass
class _Case:
    id: str
    question: str
    kind: str
    eval_user_email: str | None
    target_doc_id: str = "target"

    @property
    def is_acl_negative(self):
        return self.kind == "acl_negative"


@dataclass
class _Scores:
    faithfulness: float | None
    context_precision: float | None
    answer_relevance: float | None


@dataclass
class _Result:
    case: _Case
    target_doc_hit: bool
    target_page_hit: bool | None
    leaks: list[str]
    ragas: _Scores | None
    error: str | None = None


def test_metric_slices_group_cases_and_keep_missing_scores_unavailable():
    reporting = _eval_module("reporting")
    rows = [
        _Result(_Case("en", "What policy?", "positive", None), True, True, [], _Scores(1, 0.5, 0.7)),
        _Result(_Case("ru", "Какая политика?", "positive", "hr@example.test"), False, False, [], None),
        _Result(_Case("acl", "Restricted?", "acl_negative", None), False, None, [], _Scores(1, 1, 0)),
    ]

    slices = reporting.metric_slices(rows, "language", default_persona="employee@example.test")

    assert [item["label"] for item in slices] == ["en", "ru"]
    assert slices[0]["cases"] == 1
    assert slices[0]["doc_hit_rate"] == 1.0
    assert slices[1]["doc_hit_rate"] == 0.0
    assert slices[1]["faithfulness"] is None


def test_safe_case_diagnostics_keeps_scores_and_ranks_without_text():
    import json

    reporting = _eval_module("reporting")
    result = SimpleNamespace(
        case=SimpleNamespace(
            id="case-17",
            kind="positive",
            source_dataset="fixture-set",
            question="private question text",
            ground_truth_answer="private expected answer",
            target_doc_id="target-doc",
        ),
        target_doc_hit=True,
        target_page_hit=None,
        target_section_hit=False,
        retrieval_stage_ranks={"dense": 3, "rerank_scored": 1},
        rerank_threshold_sweep={"0.01": {"section_rank": 2, "returned": 3}},
        retrieved_doc_ids=["target-doc", "other-doc"],
        retrieved_scores=[0.82, 0.11],
        leaks=[],
        error="private exception text",
        no_answer_correct=None,
        answer_is_refusal=True,
        answer_refusal_form="exact",
        ragas=SimpleNamespace(
            faithfulness=0.9,
            context_precision=0.7,
            context_relevance_by_rank=[True, False],
            answer_relevance=0.8,
            citation_support_rate=0.75,
            citation_reference_precision=0.5,
            citation_reference_valid_count=1,
            citation_reference_count=2,
        ),
        answer="private generated answer",
        contexts=["private chunk text"],
    )

    diagnostics = reporting.safe_case_diagnostics([result])
    encoded = json.dumps(diagnostics, ensure_ascii=False)

    assert diagnostics == [
        {
            "case_id": "case-17",
            "kind": "positive",
            "source_dataset": "fixture-set",
            "target_doc_hit": True,
            "target_page_hit": None,
            "target_section_hit": False,
            "retrieval_stage_ranks": {"dense": 3, "rerank_scored": 1},
            "rerank_threshold_sweep": {"0.01": {"section_rank": 2, "returned": 3}},
            "retrieved_context_count": 2,
            "target_context_count": 1,
            "retrieved_scores": [0.82, 0.11],
            "context_relevance_by_rank": [True, False],
            "faithfulness": 0.9,
            "context_precision": 0.7,
            "answer_relevance": 0.8,
            "citation_support_rate": 0.75,
            "citation_reference_precision": 0.5,
            "citation_reference_valid_count": 1,
            "citation_reference_count": 2,
            "acl_leak_count": 0,
            "case_error": True,
            "no_answer_correct": None,
            "answer_is_refusal": True,
            "answer_refusal_form": "exact",
        }
    ]
    assert "private" not in encoded


def test_provenance_contains_only_non_secret_configuration_fingerprints():
    provenance = _eval_module("provenance")

    config = provenance.evaluation_config()

    assert config["embedding_model"]
    assert config["reranker_model"]
    assert config["llm_model"]
    assert len(config["system_prompt_sha256"]) == 64
    assert "api_key" not in config
    assert "base_url" not in config
    assert all("url" not in key for key in config)


def test_capture_metadata_records_reproducibility_fields(tmp_path, monkeypatch):
    provenance = _eval_module("provenance")
    dataset = tmp_path / "dataset.json"
    dataset.write_bytes(b'{"items": []}\n')
    config = {
        "embedding_model": "embedding-v1",
        "reranker_model": "reranker-v2",
        "llm_model": "chat-v3",
        "judge_model": "judge-v4",
        "dense_top_k": 25,
        "sparse_top_k": 25,
        "rrf_top_k": 15,
        "rrf_k": 60,
        "rerank_top_k": 4,
        "rerank_threshold": 0.25,
        "hnsw_iterative_scan": "relaxed_order",
        "hnsw_max_scan_tuples": 20000,
    }
    monkeypatch.setattr(provenance, "code_revision", lambda: "a" * 40)
    monkeypatch.setattr(provenance, "working_tree_dirty", lambda: True)

    metadata = provenance.capture_metadata(
        dataset,
        evaluation_profile="multilingual-compact",
        timestamp="2026-11-06T12:00:00+00:00",
        retrieval_only=False,
        configuration=config,
        runtime_parameters={
            "concurrency": 4,
            "embedding_batch_size": 8,
            "rerank_batch_size": 32,
            "limit": 0,
        },
    )

    assert metadata["git_commit_sha"] == "a" * 40
    assert metadata["working_tree_dirty"] is True
    assert metadata["dataset_sha256"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert metadata["evaluation_profile"] == "multilingual-compact"
    assert metadata["embedding_model_identifier"] == "embedding-v1"
    assert metadata["reranker_model_identifier"] == "reranker-v2"
    assert metadata["llm_model_identifier"] == "chat-v3"
    assert metadata["judge_model_identifier"] == "judge-v4"
    assert metadata["retrieval_parameters"] == {
        "dense_top_k": 25,
        "sparse_top_k": 25,
        "rrf_top_k": 15,
        "rrf_k": 60,
        "hnsw_iterative_scan": "relaxed_order",
        "hnsw_max_scan_tuples": 20000,
    }
    assert metadata["reranking_parameters"] == {
        "top_k": 4,
        "threshold": 0.25,
        "batch_size": 32,
    }
    assert metadata["runtime_parameters"] == {
        "concurrency": 4,
        "embedding_batch_size": 8,
        "limit": 0,
        "retrieval_only": False,
    }
    assert metadata["timestamp"] == "2026-11-06T12:00:00+00:00"
    assert metadata["evaluation_framework_version"] != ""
    assert json.loads(json.dumps(metadata)) == metadata


def test_capture_metadata_marks_missing_values_and_retrieval_only_models(tmp_path, monkeypatch):
    provenance = _eval_module("provenance")
    dataset = tmp_path / "dataset.json"
    dataset.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(provenance, "code_revision", lambda: "unavailable")
    monkeypatch.setattr(provenance, "working_tree_dirty", lambda: "unavailable")

    metadata = provenance.capture_metadata(
        dataset,
        evaluation_profile="current",
        timestamp="2026-11-06T12:00:00+00:00",
        retrieval_only=True,
        configuration={"embedding_model": "", "reranker_model": "reranker-v1"},
    )

    assert metadata["git_commit_sha"] == "unavailable"
    assert metadata["working_tree_dirty"] == "unavailable"
    assert metadata["embedding_model_identifier"] == "unavailable"
    assert metadata["llm_model_identifier"] == "not_run"
    assert metadata["judge_model_identifier"] == "not_run"
    assert metadata["retrieval_parameters"]["dense_top_k"] == "unavailable"
    assert metadata["reranking_parameters"]["batch_size"] == "unavailable"


def test_missing_git_sha_is_reported_as_unavailable(tmp_path, monkeypatch):
    provenance = _eval_module("provenance")
    monkeypatch.delenv("DOCWISE_GIT_REVISION", raising=False)
    monkeypatch.setattr(provenance.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=""))

    assert provenance.code_revision(tmp_path) == "unavailable"


def test_dirty_working_tree_is_reported(monkeypatch, tmp_path):
    provenance = _eval_module("provenance")
    monkeypatch.delenv("DOCWISE_GIT_DIRTY", raising=False)
    monkeypatch.setattr(
        provenance.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=" M eval/provenance.py\n"),
    )

    assert provenance.working_tree_dirty(tmp_path) is True


def test_new_report_metadata_omits_prompts_answers_and_custom_emails():
    run_eval = _eval_module("run_eval")
    private_question = "private prompt text must not be published"
    private_answer = "private generated answer must not be published"
    private_context = "private document contents must not be published"
    private_email = "private.person@example.test"
    case = run_eval.GoldenCase(
        id="safe-case-id",
        question=private_question,
        ground_truth_answer="private expected answer",
        target_doc_id=None,
        eval_user_email=private_email,
        source_dataset="synthetic-fixture",
    )
    result = run_eval.CaseResult(
        case=case,
        answer=private_answer,
        retrieved_doc_ids=[],
        retrieved_pages=[],
        contexts=[private_context],
        leaks=[],
        target_doc_hit=True,
        target_page_hit=None,
    )
    metadata = {
        "git_commit_sha": "a" * 40,
        "working_tree_dirty": False,
        "dataset_sha256": "b" * 64,
        "evaluation_profile": "current",
        "embedding_model_identifier": "embedding-v1",
        "reranker_model_identifier": "reranker-v1",
        "llm_model_identifier": "chat-v1",
        "judge_model_identifier": "judge-v1",
        "retrieval_parameters": {"dense_top_k": 25},
        "reranking_parameters": {"top_k": 4},
        "timestamp": "2026-11-06T12:00:00+00:00",
        "evaluation_framework_version": "not_applicable",
    }
    summary = run_eval.EvalSummary(
        private_email,
        "2026-11-06T12:00:00+00:00",
        "a" * 40,
        "b" * 64,
        results=[result],
        metadata=metadata,
    )

    report = run_eval.render_report(summary)

    assert "## Run metadata" in report
    assert "git_commit_sha" in report
    assert "retrieval_parameters" in report
    assert private_question not in report
    assert private_answer not in report
    assert private_context not in report
    assert private_email not in report


@pytest.mark.parametrize(
    "leaks, errors, positives, target_hits, expected",
    [(0, 0, 33, 1, True), (1, 0, 33, 1, False), (0, 1, 33, 1, False), (0, 0, 33, 0, False), (0, 0, 0, 0, True)],
)
def test_eval_gate_rejects_acl_errors_and_completely_empty_positive_retrieval(
    leaks, errors, positives, target_hits, expected
):
    reporting = _eval_module("reporting")

    assert (
        reporting.run_passes(
            leaks=leaks,
            errors=errors,
            positive_cases=positives,
            target_doc_hits=target_hits,
        )
        is expected
    )


def test_eval_sets_rls_organization_from_resolved_principal_before_retrieval(monkeypatch):
    run_eval = _eval_module("run_eval")
    organization_id = uuid4()
    events = []
    monkeypatch.setattr(
        run_eval,
        "bind_session_rls",
        lambda db, *, organization_id: events.append(("rls", organization_id)),
        raising=False,
    )

    def fake_retrieve(db, user, question):
        events.append(("retrieve", None))
        return SimpleNamespace(chunks=[])

    monkeypatch.setattr(run_eval, "retrieve", fake_retrieve)
    case = run_eval.GoldenCase(
        id="rls-context",
        question="What is the policy?",
        ground_truth_answer="A policy.",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000001",
    )

    run_eval._run_case(
        object(),
        SimpleNamespace(organization_id=organization_id),
        case,
        retrieval_only=True,
    )

    assert events == [("rls", organization_id), ("retrieve", None)]


def test_docx_eval_target_section_is_measured_without_inventing_a_page_number(monkeypatch):
    run_eval = _eval_module("run_eval")
    doc_id = "aaaaaaaa-1111-4111-8111-000000000010"
    monkeypatch.setattr(run_eval, "bind_session_rls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        run_eval,
        "retrieve",
        lambda *_args, **_kwargs: SimpleNamespace(
            chunks=[
                SimpleNamespace(
                    document_id=doc_id,
                    page_number=0,
                    section_title="Рабочее время",
                    content="09:00",
                    score=0.9,
                )
            ]
        ),
    )
    case = run_eval.GoldenCase(
        id="docx-section",
        question="Во сколько начинается рабочий день?",
        ground_truth_answer="В 09:00.",
        target_doc_id=doc_id,
        target_section="Рабочее время",
    )

    result = run_eval._run_case(object(), SimpleNamespace(organization_id=uuid4()), case, retrieval_only=True)

    assert result.target_page_hit is None
    assert result.target_section_hit is True


def test_retrieval_case_records_target_section_rank_at_every_pipeline_stage(monkeypatch):
    run_eval = _eval_module("run_eval")
    doc_id = "aaaaaaaa-1111-4111-8111-000000000010"

    def hit(section_title, score=0.5):
        return SimpleNamespace(document_id=doc_id, section_title=section_title, score=score)

    retrieval = SimpleNamespace(
        chunks=[
            SimpleNamespace(
                document_id=doc_id,
                page_number=0,
                section_title="target",
                content="text",
                score=0.9,
            )
        ],
        dense=[hit("other"), hit("target")],
        sparse=[hit("target")],
        rrf=[hit("other"), hit("target")],
        rerank_scored=[hit("other"), hit("target")],
        rerank_thresholded=[hit("target")],
        reranked=[hit("target")],
    )
    monkeypatch.setattr(run_eval, "bind_session_rls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(run_eval, "retrieve", lambda *_args, **_kwargs: retrieval)
    case = run_eval.GoldenCase(
        id="stage-diagnostics",
        question="Where is the target?",
        ground_truth_answer="text",
        target_doc_id=doc_id,
        target_section="target",
    )

    result = run_eval._run_case(object(), SimpleNamespace(organization_id=uuid4()), case, retrieval_only=True)

    assert result.retrieval_stage_ranks == {
        "dense": 2,
        "sparse": 1,
        "rrf": 2,
        "rerank_scored": 2,
        "rerank_thresholded": 1,
        "reranked": 1,
    }


def test_refusal_without_context_is_not_scored_as_perfect_faithfulness_or_precision(monkeypatch):
    metrics = _eval_module("metrics")
    monkeypatch.setattr(metrics, "_answer_relevance", lambda *_args: 0.0)

    scores = metrics.score_case(
        question="What is documented?",
        answer=metrics.NO_CONTEXT_ANSWER,
        contexts=[],
        ground_truth="A policy.",
        include_answer_relevance=True,
    )

    assert scores.faithfulness is None
    assert scores.context_precision is None
    assert scores.answer_relevance == 0.0


def test_refusal_with_context_keeps_retrieval_precision_but_not_faithfulness(monkeypatch):
    metrics = _eval_module("metrics")
    monkeypatch.setattr(metrics, "_context_relevance_flags", lambda *_args: [False, True])

    scores = metrics.score_case(
        question="What is documented?",
        answer=metrics.NO_CONTEXT_ANSWER,
        contexts=["Other text.", "A policy."],
        ground_truth="A policy.",
        include_answer_relevance=True,
    )

    assert scores.faithfulness is None
    assert scores.context_precision == 0.5
    assert scores.context_relevance_by_rank == [False, True]
    assert scores.answer_relevance == 0.0


def test_context_relevance_verdicts_keep_retrieval_order_and_default_missing_to_false(monkeypatch):
    metrics = _eval_module("metrics")
    monkeypatch.setattr(
        metrics,
        "_complete_json",
        lambda _messages: {
            "verdicts": [
                {"index": 3, "relevant": True},
                {"index": 1, "relevant": True},
                {"index": 2, "relevant": False},
            ]
        },
    )

    flags = metrics._context_relevance_flags("Question", "Answer", ["a", "b", "c"])

    assert flags == [True, False, True]


def test_eval_is_refusal_recognizes_ru_and_en():
    metrics = _eval_module("metrics")

    assert metrics.is_refusal(metrics.NO_CONTEXT_ANSWER)
    assert metrics.is_refusal("The provided documents do not contain information on this question.")
    assert metrics.is_refusal("Answer: The provided documents do not contain information on this question.")
    assert not metrics.is_refusal("The document says the office opens at nine.")


def test_eval_refusal_classifier_distinguishes_embedded_phrase_from_exact_refusal():
    metrics = _eval_module("metrics")

    assert metrics.classify_refusal(metrics.NO_CONTEXT_ANSWER) == "exact"
    assert metrics.classify_refusal(
        "Answer: The provided documents do not contain information on this question."
    ) == "exact"
    assert metrics.classify_refusal(
        "The provided documents do not contain information on this question. "
        "However, the policy says access starts at nine."
    ) == "embedded"
    assert metrics.classify_refusal("The office opens at nine.") == "none"
    assert metrics.classify_refusal("") == "empty"
    assert not metrics.is_refusal(
        "The provided documents do not contain information on this question. "
        "However, the policy says access starts at nine."
    )


def test_eval_empty_retrieval_uses_localized_refusal(monkeypatch):
    run_eval = _eval_module("run_eval")
    metrics = _eval_module("metrics")

    def unexpected_generation(_messages):
        raise AssertionError("empty retrieval should not call the LLM")

    monkeypatch.setattr(run_eval, "stream_openai", unexpected_generation)

    assert run_eval._generate("What do the documents say?", []) == (
        "The provided documents do not contain information on this question."
    )
    assert run_eval._generate("Что говорят документы?", []) == metrics.NO_CONTEXT_ANSWER


def test_deferred_answer_relevance_scores_zero_when_judge_generates_no_questions(monkeypatch):
    metrics = _eval_module("metrics")
    monkeypatch.setattr(metrics, "_complete_json", lambda _messages: {"questions": []})

    scores = metrics.score_case(
        question="question",
        answer="answer",
        contexts=[],
        ground_truth="answer",
        include_answer_relevance=True,
        defer_answer_relevance=True,
    )

    assert scores.answer_relevance == 0.0
    assert scores.relevance_questions == []


def test_report_shows_generation_coverage_and_retrieval_stages_without_text():
    run_eval = _eval_module("run_eval")
    target_id = "aaaaaaaa-1111-4111-8111-000000000010"
    case = run_eval.GoldenCase(
        id="coverage-case",
        question="What is documented?",
        ground_truth_answer="A policy.",
        target_doc_id=target_id,
        target_section="MIRACL passage 1#2",
        source_dataset="MIRACL v1.0 dev",
    )
    result = run_eval.CaseResult(
        case=case,
        answer=run_eval.no_context_answer(case.question),
        retrieved_doc_ids=[],
        retrieved_pages=[],
        contexts=[],
        leaks=[],
        target_doc_hit=False,
        target_page_hit=None,
        target_section_hit=False,
        ragas=run_eval.RagasScores(None, None, 0.0),
        retrieval_stage_ranks={
            "dense": None,
            "sparse": None,
            "rrf": None,
            "rerank_scored": None,
            "rerank_thresholded": None,
            "reranked": None,
        },
    )
    summary = run_eval.EvalSummary("eval@example.test", "now", "rev", "hash", results=[result])

    report = run_eval.render_report(summary)

    assert "## Response coverage" in report
    assert "Exact refusals | 1 / 1" in report
    assert "## Retrieval stage diagnostics" in report
    assert "rerank_scored" in report
    assert "rerank_thresholded" in report
    assert "Threshold simulation from the same reranker scores" in report
    assert "MIRACL v1.0 dev" in report
    assert "What is documented?" not in report
    assert "A policy." not in report


def test_report_separates_regular_answers_exact_refusals_and_embedded_phrases():
    run_eval = _eval_module("run_eval")
    answers = [
        ("The office opens at nine.", "none"),
        (run_eval.no_context_answer("Что говорят документы?"), "exact"),
        (
            "The provided documents do not contain information on this question. "
            "However, the policy says access starts at nine.",
            "embedded",
        ),
        ("", "empty"),
    ]
    results = []
    for index, (answer, form) in enumerate(answers):
        case = run_eval.GoldenCase(
            id=f"coverage-{index}",
            question=f"Question {index}?",
            ground_truth_answer="A fact.",
            target_doc_id=None,
        )
        results.append(
            run_eval.CaseResult(
                case=case,
                answer=answer,
                retrieved_doc_ids=[],
                retrieved_pages=[],
                contexts=["A context."],
                leaks=[],
                target_doc_hit=True,
                target_page_hit=None,
                ragas=run_eval.RagasScores(None, 1.0, 0.0),
                answer_refusal_form=form,
            )
        )
    summary = run_eval.EvalSummary("eval@example.test", "now", "rev", "hash", results=results)

    report = run_eval.render_report(summary)

    assert "| Regular answers | 1 / 4 |" in report
    assert "| Exact refusals | 1 / 4 |" in report
    assert "| Embedded refusal phrases | 1 / 4 |" in report
    assert "| Empty responses | 1 / 4 |" in report


def test_report_lists_stage_ranks_for_exact_section_misses():
    run_eval = _eval_module("run_eval")
    case = run_eval.GoldenCase(
        id="miracl-weak-case",
        question="Which passage covers the named topic?",
        ground_truth_answer="A fact.",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000010",
        target_section="MIRACL passage 1#2",
        source_dataset="MIRACL v1.0 dev",
    )
    result = run_eval.CaseResult(
        case=case,
        answer="A fact.",
        retrieved_doc_ids=[],
        retrieved_pages=[],
        contexts=[],
        leaks=[],
        target_doc_hit=False,
        target_page_hit=None,
        target_section_hit=False,
        ragas=run_eval.RagasScores(None, None, None),
        retrieval_stage_ranks={
            "dense": 2,
            "sparse": None,
            "rrf": 5,
            "rerank_scored": 1,
            "rerank_thresholded": None,
            "reranked": None,
        },
        rerank_threshold_sweep={
            "0.10": {"section_rank": None},
            "0.25": {"section_rank": 3},
        },
    )
    summary = run_eval.EvalSummary("eval@example.test", "now", "rev", "hash", results=[result])

    report = run_eval.render_report(summary)

    assert "## Exact-section misses by case" in report
    assert "miracl-weak-case" in report
    assert "| miracl-weak-case | 2 | — | 5 | 1 | — | — | 3 |" in report


def test_report_separates_no_answer_and_acl_denominators():
    run_eval = _eval_module("run_eval")
    positive_case = run_eval.GoldenCase(
        id="answerable",
        question="What is documented?",
        ground_truth_answer="A policy.",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000010",
    )
    no_answer_case = run_eval.GoldenCase(
        id="no-answer",
        question="What is the boiling point of gallium?",
        ground_truth_answer="",
        target_doc_id=None,
        kind="no_answer",
        source_dataset="synthetic-no-answer",
    )
    acl_case = run_eval.GoldenCase(
        id="acl-negative",
        question="What is the restricted policy?",
        ground_truth_answer=run_eval.no_context_answer("What is the restricted policy?"),
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000011",
        kind="acl_negative",
    )

    def result(case, *, target_hit, refusal=None):
        return run_eval.CaseResult(
            case=case,
            answer=run_eval.no_context_answer(case.question) if refusal else "answer text",
            retrieved_doc_ids=[],
            retrieved_pages=[],
            contexts=[],
            leaks=[],
            target_doc_hit=target_hit,
            target_page_hit=None,
            no_answer_correct=refusal if case.kind == "no_answer" else None,
        )

    summary = run_eval.EvalSummary(
        "eval@example.test",
        "now",
        "rev",
        "hash",
        results=[
            result(positive_case, target_hit=True),
            result(no_answer_case, target_hit=None, refusal=True),
            result(acl_case, target_hit=False),
        ],
    )

    report = run_eval.render_report(summary)

    assert len(summary.positives) == 1
    assert len(summary.no_answer_cases) == 1
    assert len(summary.acl_rows) == 1
    assert "Cases: 3 (1 positive, 1 no-answer, 1 ACL-negative)" in report
    assert "Correct no-answer refusals | 1 / 1" in report
    assert "answer text" not in report
    assert "A policy." not in report


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("The provided documents do not contain information on this question.", True),
        ("The office has a policy for that.", False),
    ],
)
def test_no_answer_cases_record_refusal_without_ragas_judging(monkeypatch, answer, expected):
    run_eval = _eval_module("run_eval")
    case = run_eval.GoldenCase(
        id="no-answer-case",
        question="What is not documented?",
        ground_truth_answer="",
        target_doc_id=None,
        kind="no_answer",
    )
    result = run_eval.CaseResult(
        case=case,
        answer="",
        retrieved_doc_ids=[],
        retrieved_pages=[],
        contexts=[],
        leaks=[],
        target_doc_hit=None,
        target_page_hit=None,
    )
    monkeypatch.setattr(run_eval, "_generate", lambda *_args: answer)
    monkeypatch.setattr(run_eval, "score_case", lambda **_kwargs: pytest.fail("no-answer case must skip Ragas judges"))

    evaluated = run_eval._evaluate_prepared_case(run_eval.PreparedCase(result, chunks=[]))

    assert evaluated.no_answer_correct is expected
    assert evaluated.ragas is None
    assert evaluated.answer == answer


def test_retrieval_only_report_shows_provenance_and_marks_generation_metrics_unavailable():
    run_eval = _eval_module("run_eval")
    case = run_eval.GoldenCase(
        id="report-case",
        question="What is the policy?",
        ground_truth_answer="A policy.",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000001",
    )
    result = run_eval.CaseResult(
        case=case,
        answer="",
        retrieved_doc_ids=[case.target_doc_id],
        retrieved_pages=[1],
        contexts=[],
        leaks=[],
        target_doc_hit=True,
        target_page_hit=True,
        ragas=run_eval.RagasScores(
            faithfulness=1.0,
            context_precision=1.0,
            answer_relevance=0.9,
            citation_support_rate=0.5,
            citation_reference_precision=0.5,
            citation_reference_valid_count=1,
            citation_reference_count=2,
        ),
    )
    summary = run_eval.EvalSummary(
        eval_user_email="eval@example.test",
        generated_at="2026-10-30T00:00:00+00:00",
        code_revision="test-revision",
        dataset_sha256="test-dataset-hash",
        config={"llm_model": "test-model"},
        results=[result],
        retrieval_only=True,
    )

    report = run_eval.render_report(summary)

    assert "`llm_model`: `test-model`" in report
    assert "Code revision: `test-revision`" in report
    assert "Golden dataset SHA-256: `test-dataset-hash`" in report
    assert "`git_commit_sha` | `unavailable`" in report
    assert "Generation quality was not evaluated" in report
    assert "| Target document hit rate | 1.000 | 1 |" in report
    assert "| Citation support | 0.500 | 1 |" in report
    assert "## Deterministic source reference check" in report
    assert "| Inline references matching retrieved sources | 1 / 2 |" in report
    assert "| Citation reference precision | 0.500 |" in report
    assert "## Quality gates" in report
    assert "| Faithfulness | n/a | n/a | N/A |" in report


def test_judge_json_parse_retries_once_before_returning_result(monkeypatch):
    metrics = _eval_module("metrics")
    responses = iter(["not json", '{"statements": []}'])
    calls = []

    def complete_openai(messages, *, temperature):
        calls.append((messages, temperature))
        return next(responses), None

    monkeypatch.setattr(metrics, "complete_openai", complete_openai)

    result = metrics._complete_json([])

    assert result == {"statements": []}
    assert len(calls) == 2


def test_judge_json_parse_fails_after_retry_instead_of_scoring_invalid_payload(monkeypatch):
    metrics = _eval_module("metrics")
    monkeypatch.setattr(metrics, "complete_openai", lambda *_args, **_kwargs: ("not json", None))

    with pytest.raises(metrics.EvalJudgeError):
        metrics._complete_json([])


def test_quality_gates_accept_exact_thresholds_and_reject_any_lower_value():
    gates = _eval_module("quality_gates")

    at_floor = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=0.98,
        target_page_hit_rate=0.98,
        faithfulness=0.80,
        context_precision=0.975,
        answer_relevance=0.827,
        retrieval_only=False,
        no_answer_refusal_rate=1.0,
    )
    below_floor = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=0.979,
        target_page_hit_rate=0.98,
        faithfulness=0.80,
        context_precision=0.975,
        answer_relevance=0.827,
        retrieval_only=False,
        no_answer_refusal_rate=1.0,
    )

    assert gates.all_gates_pass(at_floor)
    assert not gates.all_gates_pass(below_floor)
    assert next(gate for gate in below_floor if gate.name == "Target document hit rate").status == "FAIL"


def test_no_answer_refusal_gate_fails_when_corpus_supported_answer_is_given():
    gates = _eval_module("quality_gates")

    results = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=1.0,
        target_page_hit_rate=None,
        faithfulness=1.0,
        context_precision=1.0,
        answer_relevance=1.0,
        no_answer_refusal_rate=0.75,
        retrieval_only=False,
    )

    gate = next(item for item in results if item.name == "No-answer refusal rate")
    assert gate.status == "FAIL"
    assert gate.threshold == ">= 0.800"


def test_full_generation_gate_fails_when_no_answer_cases_are_absent():
    gates = _eval_module("quality_gates")

    results = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=1.0,
        target_page_hit_rate=1.0,
        faithfulness=1.0,
        context_precision=1.0,
        answer_relevance=1.0,
        retrieval_only=False,
    )

    no_answer_gate = next(item for item in results if item.name == "No-answer refusal rate")
    assert no_answer_gate.status == "FAIL"
    assert no_answer_gate.threshold == ">= 0.800"
    assert not gates.all_gates_pass(results)


def test_quality_gates_fail_full_run_on_missing_metric_but_mark_generation_na_for_retrieval_only():
    gates = _eval_module("quality_gates")

    full = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=1.0,
        target_page_hit_rate=1.0,
        faithfulness=None,
        context_precision=None,
        answer_relevance=None,
        retrieval_only=False,
    )
    retrieval = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=1.0,
        target_page_hit_rate=1.0,
        faithfulness=None,
        context_precision=None,
        answer_relevance=None,
        retrieval_only=True,
    )

    assert not gates.all_gates_pass(full)
    assert gates.all_gates_pass(retrieval)
    assert [gate.status for gate in retrieval if gate.name in gates.GENERATION_GATES] == ["N/A"] * 4


def test_quality_gate_marks_target_pages_na_when_dataset_has_no_page_labels():
    gates = _eval_module("quality_gates")

    results = gates.evaluate_gates(
        leaks=0,
        errors=0,
        target_doc_hit_rate=0.925,
        target_page_hit_rate=None,
        faithfulness=1.0,
        context_precision=0.882,
        answer_relevance=0.507,
        retrieval_only=False,
    )

    page_gate = next(gate for gate in results if gate.name == "Target page hit rate")
    assert page_gate.status == "N/A"
    assert page_gate.threshold == "n/a"


def test_answer_relevance_regression_gate_uses_comparable_english_slice_only():
    run_eval = _eval_module("run_eval")
    english = run_eval.CaseResult(
        case=run_eval.GoldenCase("en", "What is the rule?", "The rule.", "aaaaaaaa-1111-4111-8111-000000000001"),
        answer="The rule.",
        retrieved_doc_ids=["aaaaaaaa-1111-4111-8111-000000000001"],
        retrieved_pages=[1],
        contexts=["The rule."],
        leaks=[],
        target_doc_hit=True,
        target_page_hit=True,
        ragas=run_eval.RagasScores(1.0, 1.0, 0.82),
    )
    russian = run_eval.CaseResult(
        case=run_eval.GoldenCase("ru", "Какое правило?", "Правило.", "aaaaaaaa-1111-4111-8111-000000000001"),
        answer="Правило.",
        retrieved_doc_ids=["aaaaaaaa-1111-4111-8111-000000000001"],
        retrieved_pages=[],
        contexts=["Правило."],
        leaks=[],
        target_doc_hit=True,
        target_page_hit=None,
        ragas=run_eval.RagasScores(1.0, 1.0, 0.2),
    )
    summary = run_eval.EvalSummary("eval@example.test", "now", "rev", "hash", results=[english, russian])

    gate = next(item for item in run_eval._quality_gates(summary) if item.name == "Answer Relevance (English)")

    assert gate.observed == pytest.approx(0.82)
    assert gate.status == "FAIL"


def test_answer_relevance_batch_encodes_many_cases_in_one_call_per_profile(monkeypatch):
    metrics = _eval_module("metrics")
    embed_calls = []
    vectors = {
        "q1": [1.0, 0.0],
        "g1": [1.0, 0.0],
        "g2": [0.0, 1.0],
        "q2": [0.0, 1.0],
        "g3": [0.0, 1.0],
        "вопрос": [1.0, 0.0],
        "ответ": [1.0, 0.0],
    }

    def embed(texts, profile):
        embed_calls.append((list(texts), profile))
        return [vectors[text] for text in texts]

    monkeypatch.setattr(metrics, "embed_texts_for_profile", embed)

    scores = metrics.score_answer_relevance_batch(
        [
            ("q1", ["g1", "g2"]),
            ("q2", ["g3"]),
            ("вопрос", ["ответ"]),
            ("empty", []),
        ]
    )

    assert scores == pytest.approx([0.5, 1.0, 1.0, 0.0])
    assert embed_calls == [
        (["q1", "g1", "g2", "q2", "g3"], "current"),
        (["вопрос", "ответ"], "multilingual-compact"),
    ]


def test_eval_releases_reranker_cache_after_retrieval(monkeypatch):
    run_eval = _eval_module("run_eval")
    from app.services.retrieval import reranker

    monkeypatch.setattr(reranker, "_reranker", object())

    run_eval._release_reranker_after_retrieval()

    assert reranker._reranker is None


@pytest.mark.parametrize(("leaks", "errors", "expected_name"), [(1, 0, "ACL leaks"), (0, 1, "Case errors")])
def test_quality_gates_always_fail_for_acl_leaks_or_case_errors(leaks, errors, expected_name):
    gates = _eval_module("quality_gates")

    results = gates.evaluate_gates(
        leaks=leaks,
        errors=errors,
        target_doc_hit_rate=1.0,
        target_page_hit_rate=1.0,
        faithfulness=1.0,
        context_precision=1.0,
        answer_relevance=1.0,
        retrieval_only=False,
    )

    assert not gates.all_gates_pass(results)
    assert next(gate for gate in results if gate.name == expected_name).status == "FAIL"
