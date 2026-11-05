"""Pure helpers for deterministic evaluation report slices."""

from __future__ import annotations

import math
from statistics import mean
from typing import Literal

SliceDimension = Literal["language", "persona", "kind", "source_dataset"]
RETRIEVAL_STAGES = (
    "dense",
    "sparse",
    "rrf",
    "rerank_scored",
    "rerank_thresholded",
    "reranked",
)
RERANK_THRESHOLD_SWEEP = (0.10, 0.15, 0.20, 0.25, 0.30)


def question_language(question: str) -> str:
    """Bucket a question by Unicode script; this is a coarse, deterministic signal."""
    cyrillic = any("\u0400" <= char <= "\u04ff" for char in question)
    latin = any(char.isascii() and char.isalpha() for char in question)
    if cyrillic and latin:
        return "mixed"
    if cyrillic:
        return "ru"
    if latin:
        return "en"
    return "unknown"


def safe_case_diagnostics(results) -> list[dict[str, object]]:
    """Export case metrics and retrieval scores without question, answer, or passage text."""
    output: list[dict[str, object]] = []
    for row in results:
        ragas = getattr(row, "ragas", None)
        target_doc_id = getattr(row.case, "target_doc_id", None)
        retrieved_doc_ids = list(getattr(row, "retrieved_doc_ids", ()) or ())
        output.append(
            {
                "case_id": row.case.id,
                "kind": row.case.kind,
                "source_dataset": getattr(row.case, "source_dataset", None),
                "target_doc_hit": row.target_doc_hit,
                "target_page_hit": row.target_page_hit,
                "target_section_hit": getattr(row, "target_section_hit", None),
                "retrieval_stage_ranks": dict(getattr(row, "retrieval_stage_ranks", {}) or {}),
                "rerank_threshold_sweep": dict(getattr(row, "rerank_threshold_sweep", {}) or {}),
                "retrieved_context_count": len(retrieved_doc_ids),
                "target_context_count": sum(doc_id == target_doc_id for doc_id in retrieved_doc_ids),
                "retrieved_scores": [float(score) for score in getattr(row, "retrieved_scores", ())],
                "context_relevance_by_rank": [
                    bool(relevant)
                    for relevant in getattr(ragas, "context_relevance_by_rank", ())
                ],
                "faithfulness": getattr(ragas, "faithfulness", None),
                "context_precision": getattr(ragas, "context_precision", None),
                "answer_relevance": getattr(ragas, "answer_relevance", None),
                "citation_support_rate": getattr(ragas, "citation_support_rate", None),
                "acl_leak_count": len(getattr(row, "leaks", ()) or ()),
                "case_error": bool(getattr(row, "error", None)),
                "no_answer_correct": getattr(row, "no_answer_correct", None),
                "answer_is_refusal": getattr(row, "answer_is_refusal", None),
                "answer_refusal_form": getattr(row, "answer_refusal_form", None),
            }
        )
    return output


def metric_slices(
    results, dimension: SliceDimension, *, default_persona: str
) -> list[dict[str, object]]:
    """Aggregate positive-case metrics by language, evaluator persona, or case kind."""
    if dimension not in {"language", "persona", "kind", "source_dataset"}:
        raise ValueError(f"Unsupported metric slice: {dimension}")

    groups: dict[str, list] = {}
    for row in results:
        if row.case.kind != "positive":
            continue
        if dimension == "language":
            label = question_language(row.case.question)
        elif dimension == "persona":
            label = row.case.eval_user_email or default_persona
        elif dimension == "kind":
            label = row.case.kind
        else:
            label = row.case.source_dataset
        groups.setdefault(label, []).append(row)

    output: list[dict[str, object]] = []
    for label, rows in sorted(groups.items()):
        positive = [row for row in rows if row.case.kind == "positive"]
        pages = [
            row.target_page_hit for row in positive if row.target_page_hit is not None
        ]
        sections = [
            getattr(row, "target_section_hit", None)
            for row in positive
            if getattr(row, "target_section_hit", None) is not None
        ]
        output.append(
            {
                "label": label,
                "cases": len(rows),
                "doc_hit_rate": _avg([float(row.target_doc_hit) for row in positive]),
                "page_hit_rate": _avg([float(value) for value in pages]),
                "section_hit_rate": _avg([float(value) for value in sections]),
                "faithfulness": _avg(
                    [row.ragas.faithfulness if row.ragas else None for row in positive]
                ),
                "context_precision": _avg(
                    [
                        row.ragas.context_precision if row.ragas else None
                        for row in positive
                    ]
                ),
                "answer_relevance": _avg(
                    [
                        row.ragas.answer_relevance if row.ragas else None
                        for row in positive
                    ]
                ),
                "citation_support_rate": _avg(
                    [
                        getattr(row.ragas, "citation_support_rate", None) if row.ragas else None
                        for row in positive
                    ]
                ),
                "errors": sum(1 for row in rows if row.error),
            }
        )
    return output


def run_passes(
    *, leaks: int, errors: int, positive_cases: int, target_doc_hits: int
) -> bool:
    has_retrieval_signal = positive_cases == 0 or target_doc_hits > 0
    return leaks == 0 and errors == 0 and has_retrieval_signal


def stage_target_ranks(retrieval, *, target_doc_id: str, target_section: str | None) -> dict[str, int | None]:
    """Return 1-based first ranks for an exact target section, without retaining snippets."""
    ranks: dict[str, int | None] = {}
    for stage in RETRIEVAL_STAGES:
        hits = getattr(retrieval, stage, ()) or ()
        ranks[stage] = next(
            (
                index
                for index, hit in enumerate(hits, start=1)
                if target_section is not None
                and str(getattr(hit, "document_id", "")) == target_doc_id
                and getattr(hit, "section_title", None) == target_section
            ),
            None,
        )
    return ranks


def retrieval_stage_metrics(results) -> list[dict[str, object]]:
    """Aggregate target document and exact-section recall at retrieval pipeline stages."""
    rows = [row for row in results if row.case.kind == "positive"]
    section_rows = [row for row in rows if row.case.target_section is not None]
    output: list[dict[str, object]] = []
    for stage in RETRIEVAL_STAGES:
        doc_hits = [float(bool(getattr(row, "retrieval_stage_doc_hits", {}).get(stage))) for row in rows]
        ranks = [getattr(row, "retrieval_stage_ranks", {}).get(stage) for row in section_rows]
        output.append(
            {
                "stage": stage,
                "cases": len(rows),
                "section_cases": len(section_rows),
                "target_doc_hit_rate": _avg(doc_hits),
                "section_recall_at_1": _avg([float(rank is not None and rank <= 1) for rank in ranks]),
                "section_recall_at_4": _avg([float(rank is not None and rank <= 4) for rank in ranks]),
                "section_recall_at_10": _avg([float(rank is not None and rank <= 10) for rank in ranks]),
                "section_mrr": _avg([1.0 / rank if rank is not None else 0.0 for rank in ranks]),
            }
        )
    return output


def rerank_threshold_case_metrics(
    scored_hits,
    *,
    target_doc_id: str,
    target_section: str | None,
    thresholds: tuple[float, ...] = RERANK_THRESHOLD_SWEEP,
    top_k: int = 4,
) -> dict[str, dict[str, int | bool | None]]:
    """Simulate threshold + Top-K from the same ordered cross-encoder scores."""
    output: dict[str, dict[str, int | bool | None]] = {}
    for threshold in thresholds:
        selected = [hit for hit in scored_hits if float(hit.score) >= threshold][:top_k]
        section_rank = next(
            (
                index
                for index, hit in enumerate(selected, start=1)
                if target_section is not None
                and str(hit.document_id) == target_doc_id
                and getattr(hit, "section_title", None) == target_section
            ),
            None,
        )
        output[f"{threshold:.2f}"] = {
            "target_doc_hit": any(str(hit.document_id) == target_doc_id for hit in selected),
            "section_rank": section_rank,
            "returned": len(selected),
        }
    return output


def rerank_threshold_metrics(results) -> list[dict[str, object]]:
    """Aggregate simulated coverage/occupancy for one cross-encoder scoring pass."""
    rows = [row for row in results if row.case.kind == "positive"]
    section_rows = [row for row in rows if row.case.target_section is not None]
    output: list[dict[str, object]] = []
    for threshold in RERANK_THRESHOLD_SWEEP:
        key = f"{threshold:.2f}"
        all_values = [getattr(row, "rerank_threshold_sweep", {}).get(key, {}) for row in rows]
        section_values = [
            getattr(row, "rerank_threshold_sweep", {}).get(key, {}) for row in section_rows
        ]
        ranks = [value.get("section_rank") for value in section_values]
        output.append(
            {
                "threshold": key,
                "target_doc_hit_rate": _avg([float(bool(value.get("target_doc_hit"))) for value in all_values]),
                "section_cases": len(section_rows),
                "section_recall_at_1": _avg([float(rank is not None and rank <= 1) for rank in ranks]),
                "section_recall_at_4": _avg([float(rank is not None and rank <= 4) for rank in ranks]),
                "section_mrr": _avg([1.0 / rank if rank is not None else 0.0 for rank in ranks]),
                "mean_returned": _avg([float(value.get("returned", 0)) for value in all_values]),
                "empty_rate": _avg([float(value.get("returned", 0) == 0) for value in all_values]),
            }
        )
    return output


def runtime_timing_metrics(results) -> list[dict[str, float | int | str]]:
    """Aggregate numeric stage timings without including case inputs or outputs."""
    stages = ("retrieval_total", "db_search")
    output: list[dict[str, float | int | str]] = []
    for stage in stages:
        values = [
            float(value)
            for row in results
            if (value := getattr(row, "stage_timings_ms", {}).get(stage)) is not None
        ]
        if not values:
            continue
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError(f"{stage} timings must be finite and non-negative")
        output.append(
            {
                "stage": stage,
                "cases": len(values),
                "total_ms": sum(values),
                "mean_ms": mean(values) if values else 0.0,
            }
        )
    return output


def _avg(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    return mean(present) if present else None
