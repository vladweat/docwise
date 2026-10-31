"""Initial regression floors for the golden-set RAG evaluation."""

from __future__ import annotations

from dataclasses import dataclass

TARGET_HIT_FLOOR = 0.98
FAITHFULNESS_FLOOR = 0.80
CONTEXT_PRECISION_FLOOR = 0.975
ANSWER_RELEVANCE_FLOOR = 0.827
NO_ANSWER_REFUSAL_FLOOR = 0.80

GENERATION_GATES = (
    "Faithfulness",
    "Context Precision",
    "Answer Relevance (English)",
    "No-answer refusal rate",
)


@dataclass(frozen=True)
class GateResult:
    name: str
    observed: int | float | None
    threshold: str
    status: str


def _minimum_gate(name: str, observed: float | None, threshold: float) -> GateResult:
    return GateResult(
        name=name,
        observed=observed,
        threshold=f">= {threshold:.3f}",
        status="PASS" if observed is not None and observed >= threshold else "FAIL",
    )


def _zero_gate(name: str, observed: int) -> GateResult:
    return GateResult(name=name, observed=observed, threshold="= 0", status="PASS" if observed == 0 else "FAIL")


def _optional_minimum_gate(name: str, observed: float | None, threshold: float) -> GateResult:
    if observed is None:
        return GateResult(name=name, observed=None, threshold="n/a", status="N/A")
    return _minimum_gate(name, observed, threshold)


def evaluate_gates(
    *,
    leaks: int,
    errors: int,
    target_doc_hit_rate: float | None,
    target_page_hit_rate: float | None,
    faithfulness: float | None,
    context_precision: float | None,
    answer_relevance: float | None,
    retrieval_only: bool,
    no_answer_refusal_rate: float | None = None,
) -> list[GateResult]:
    """Evaluate aggregate gates; absent full-run judge scores are failures."""
    results = [
        _zero_gate("ACL leaks", leaks),
        _zero_gate("Case errors", errors),
        _minimum_gate("Target document hit rate", target_doc_hit_rate, TARGET_HIT_FLOOR),
        _optional_minimum_gate("Target page hit rate", target_page_hit_rate, TARGET_HIT_FLOOR),
    ]
    if retrieval_only:
        results.extend(GateResult(name, None, "n/a", "N/A") for name in GENERATION_GATES)
    else:
        results.extend(
            [
                _minimum_gate("Faithfulness", faithfulness, FAITHFULNESS_FLOOR),
                _minimum_gate("Context Precision", context_precision, CONTEXT_PRECISION_FLOOR),
                _minimum_gate("Answer Relevance (English)", answer_relevance, ANSWER_RELEVANCE_FLOOR),
                _minimum_gate("No-answer refusal rate", no_answer_refusal_rate, NO_ANSWER_REFUSAL_FLOOR),
            ]
        )
    return results


def all_gates_pass(results: list[GateResult]) -> bool:
    return bool(results) and all(result.status != "FAIL" for result in results)
