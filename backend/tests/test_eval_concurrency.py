"""Bounded, ordered concurrency helpers used by the RAG evaluator."""

from __future__ import annotations

import importlib.util
import sys
from types import SimpleNamespace
import threading
import time
from pathlib import Path

import pytest


def _eval_module(name: str):
    eval_dir = Path(__file__).resolve().parents[2] / "eval"
    spec = importlib.util.spec_from_file_location(f"eval_{name}", eval_dir / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_bounded_map_runs_concurrently_but_preserves_input_order():
    concurrency = _eval_module("concurrency")
    guard = threading.Lock()
    active = 0
    max_active = 0

    def evaluate(value: int) -> int:
        nonlocal active, max_active
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.03 * (5 - value))
        with guard:
            active -= 1
        return value * 10

    results = concurrency.map_bounded(range(5), evaluate, max_workers=2)

    assert results == [0, 10, 20, 30, 40]
    assert 1 < max_active <= 2


@pytest.mark.parametrize("max_workers", [0, -1])
def test_bounded_map_rejects_non_positive_worker_count(max_workers: int):
    concurrency = _eval_module("concurrency")

    with pytest.raises(ValueError, match="max_workers must be positive"):
        concurrency.map_bounded([1], lambda value: value, max_workers=max_workers)


def test_bounded_map_reports_each_completion_including_serial_mode():
    concurrency = _eval_module("concurrency")
    completed = []

    results = concurrency.map_bounded(
        ["first", "second"],
        str.upper,
        max_workers=1,
        on_complete=lambda index, item, result: completed.append((index, item, result)),
    )

    assert results == ["FIRST", "SECOND"]
    assert completed == [(0, "first", "FIRST"), (1, "second", "SECOND")]


def test_bounded_map_keeps_case_local_error_values():
    concurrency = _eval_module("concurrency")

    def evaluate(value: str) -> str:
        if value == "bad":
            return "case error"
        return f"done:{value}"

    assert concurrency.map_bounded(["a", "bad", "c"], evaluate, max_workers=2) == [
        "done:a",
        "case error",
        "done:c",
    ]


def test_eval_generation_does_not_send_leaked_chunks_to_the_prompt(monkeypatch):
    run_eval = _eval_module("run_eval")
    result = SimpleNamespace(
        case=SimpleNamespace(
            id="acl-case",
            question="question",
            ground_truth_answer="answer",
            is_acl_negative=False,
            is_no_answer=False,
        ),
        leaks=["restricted-doc"],
        contexts=["[redacted restricted chunk]"],
        answer="",
        error=None,
        ragas=None,
    )
    seen_chunks = []

    def generate(_question, chunks):
        seen_chunks.extend(chunks)
        return "refusal"

    monkeypatch.setattr(run_eval, "_generate", generate)
    monkeypatch.setattr(run_eval, "score_case", lambda **_kwargs: "scores")

    evaluated = run_eval._evaluate_prepared_case(run_eval.PreparedCase(result=result, chunks=["restricted text"]))

    assert seen_chunks == []
    assert evaluated.ragas == "scores"


def test_eval_case_failure_is_recorded_without_raising_from_worker(monkeypatch):
    run_eval = _eval_module("run_eval")
    result = SimpleNamespace(
        case=SimpleNamespace(
            id="failed-case",
            question="question",
            ground_truth_answer="answer",
            is_acl_negative=False,
        ),
        leaks=[],
        contexts=["allowed text"],
        answer="",
        error=None,
        ragas=None,
    )

    def fail_generation(_question, _chunks):
        raise TimeoutError("provider timeout")

    monkeypatch.setattr(run_eval, "_generate", fail_generation)

    evaluated = run_eval._evaluate_prepared_case(run_eval.PreparedCase(result=result, chunks=["allowed text"]))

    assert evaluated.error == "provider timeout"
    assert evaluated.answer == ""


def test_eval_concurrency_argument_requires_a_positive_integer():
    run_eval = _eval_module("run_eval")

    assert run_eval._positive_int("4") == 4
    with pytest.raises(run_eval.argparse.ArgumentTypeError, match="positive integer"):
        run_eval._positive_int("0")
