"""Evaluation throughput diagnostics must preserve alignment and stay content-free."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

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


def test_query_embedding_batches_preserve_input_order_and_alignment():
    run_eval = _eval_module("run_eval")
    calls: list[list[str]] = []

    def embed(texts: list[str]) -> list[list[float]]:
        calls.append(list(texts))
        return [[float(index)] for index, _text in enumerate(texts)]

    vectors = run_eval.embed_questions_batched(
        ["q1", "q2", "q3", "q4", "q5"], batch_size=2, embed_fn=embed
    )

    assert calls == [["q1", "q2"], ["q3", "q4"], ["q5"]]
    assert vectors == [[0.0], [1.0], [0.0], [1.0], [0.0]]
    assert len(vectors) == 5


def test_query_embedding_batches_reject_misaligned_vectors():
    run_eval = _eval_module("run_eval")

    with pytest.raises(ValueError, match="count does not match"):
        run_eval.embed_questions_batched(
            ["q1", "q2"], batch_size=2, embed_fn=lambda _texts: [[1.0]]
        )


def test_reranker_pairs_batch_and_restore_input_order():
    run_eval = _eval_module("run_eval")
    calls: list[list[tuple[str, str]]] = []

    def score_pairs(pairs: list[tuple[str, str]]) -> list[float]:
        calls.append(list(pairs))
        return [float(len(query) * 10 + len(document)) for query, document in pairs]

    groups = [
        [("q1", "doc-a"), ("q1", "doc-bb")],
        [("question-2", "doc-c")],
    ]
    scores = run_eval.score_rerank_pairs_batched(groups, batch_size=2, score_fn=score_pairs)

    assert sorted(pair for call in calls for pair in call) == sorted(pair for group in groups for pair in group)
    assert all(len(call) <= 2 for call in calls)
    assert scores == [[25.0, 26.0], [105.0]]


def test_reranker_pair_batches_reject_misaligned_scores():
    run_eval = _eval_module("run_eval")

    with pytest.raises(ValueError, match="score count does not match"):
        run_eval.score_rerank_pairs_batched(
            [[("q", "doc")]], batch_size=2, score_fn=lambda _pairs: []
        )


def test_runtime_report_contains_safe_nonnegative_aggregate_timings():
    run_eval = _eval_module("run_eval")
    query = "PRIVATE_QUERY_SENTINEL"
    case = run_eval.GoldenCase(
        id="timed-case",
        question=query,
        ground_truth_answer="reference",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000001",
    )
    row = run_eval.CaseResult(
        case=case,
        answer="",
        retrieved_doc_ids=[],
        retrieved_pages=[],
        contexts=[],
        leaks=[],
        target_doc_hit=False,
        target_page_hit=None,
        stage_timings_ms={"db_search": 10.0, "rerank": 2.0},
    )
    summary = run_eval.EvalSummary(
        eval_user_email="eval@example.test",
        generated_at="2026-01-01T00:00:00+00:00",
        code_revision="test",
        dataset_sha256="test",
        results=[row],
        query_embedding_ms=4.0,
        query_embedding_count=1,
    )

    report = run_eval.render_report(summary)
    timing_section = report.split("## Runtime profile", 1)[1].split("\n## ", 1)[0]

    assert "Query embedding" in timing_section
    assert "DB search" in timing_section
    assert "Rerank" in timing_section
    assert "10.000" in timing_section
    assert "PRIVATE_QUERY_SENTINEL" not in timing_section


def test_runtime_report_rejects_negative_stage_timings():
    run_eval = _eval_module("run_eval")
    case = run_eval.GoldenCase(
        id="bad-timing",
        question="q",
        ground_truth_answer="a",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000001",
    )
    row = run_eval.CaseResult(
        case=case,
        answer="",
        retrieved_doc_ids=[],
        retrieved_pages=[],
        contexts=[],
        leaks=[],
        target_doc_hit=False,
        target_page_hit=None,
        stage_timings_ms={"db_search": -1.0},
    )
    summary = run_eval.EvalSummary(
        eval_user_email="eval@example.test",
        generated_at="2026-01-01T00:00:00+00:00",
        code_revision="test",
        dataset_sha256="test",
        results=[row],
    )

    with pytest.raises(ValueError, match="non-negative"):
        run_eval.render_report(summary)


def test_precomputed_query_vector_keeps_authenticated_principal_in_retrieval(monkeypatch):
    from types import SimpleNamespace
    from uuid import uuid4

    run_eval = _eval_module("run_eval")
    principal = SimpleNamespace(organization_id=uuid4(), access_roles=("employee",))
    events: list[tuple[str, object]] = []
    retrieval = SimpleNamespace(chunks=[], rerank_scored=[])
    pool = SimpleNamespace(records={}, fused=[])

    monkeypatch.setattr(
        run_eval,
        "bind_session_rls",
        lambda db, *, organization_id: events.append(("rls", organization_id)),
    )
    monkeypatch.setattr(
        run_eval,
        "hybrid_search",
        lambda db, user, query, vector: events.append(("search", (user, vector))) or pool,
    )
    monkeypatch.setattr(run_eval, "finish_retrieval", lambda *_args, **_kwargs: retrieval)
    case = run_eval.GoldenCase(
        id="precomputed-vector",
        question="question",
        ground_truth_answer="answer",
        target_doc_id="aaaaaaaa-1111-4111-8111-000000000001",
    )

    prepared = run_eval._prepare_case(object(), principal, case, query_vector=[0.25])
    assert prepared.pool is pool
    assert run_eval._finish_prepared_retrievals([prepared], batch_size=2) == 0

    assert events[0] == ("rls", principal.organization_id)
    assert events[1] == ("search", (principal, [0.25]))
    assert prepared.result.stage_timings_ms.keys() == {"db_search"}
    assert all(value >= 0 for value in prepared.result.stage_timings_ms.values())
