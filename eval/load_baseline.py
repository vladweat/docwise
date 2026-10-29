#!/usr/bin/env python3
"""Measure hybrid retrieval latency on the live indexed corpus (no LLM).

Writes reports/load_baseline.md for pilot capacity tracking. Run via `make load-baseline`.
"""

from __future__ import annotations

import argparse
import logging
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if BACKEND_DIR.is_dir():
    sys.path.insert(0, str(BACKEND_DIR))
elif Path("/app/app").is_dir():
    sys.path.insert(0, "/app")
sys.path.insert(0, str(EVAL_DIR))

from dataset import load_golden_dataset, default_dataset_path  # noqa: E402
from provenance import code_revision, dataset_sha256  # noqa: E402

from sqlalchemy import text  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.org.tenancy import resolve_principal  # noqa: E402
from app.services.retrieval import retrieve  # noqa: E402

logger = logging.getLogger("load_baseline")


def default_report_path() -> Path:
    env = os.environ.get("LOAD_BASELINE_REPORT")
    if env:
        return Path(env)
    if (REPO_ROOT / "reports").is_dir() or (REPO_ROOT / "docs").is_dir():
        return REPO_ROOT / "reports" / "load_baseline.md"
    return Path("/reports/load_baseline.md")


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _corpus_stats(db) -> dict[str, int | str]:
    settings = get_settings()
    rows = db.execute(
        text(
            """
            SELECT
              (SELECT count(*) FROM document_chunks) AS chunks,
              (SELECT count(*) FROM documents WHERE status = 'ready') AS ready_docs,
              (SELECT count(*) FROM documents WHERE status = 'failed') AS failed_docs,
              (SELECT count(DISTINCT organization_id) FROM document_chunks) AS orgs_with_chunks
            """
        )
    ).one()
    return {
        "chunks": int(rows.chunks),
        "ready_docs": int(rows.ready_docs),
        "failed_docs": int(rows.failed_docs),
        "orgs_with_chunks": int(rows.orgs_with_chunks),
        "hnsw_max_scan_tuples": str(settings.hnsw_max_scan_tuples),
        "hnsw_iterative_scan": settings.hnsw_iterative_scan,
        "rerank_threshold": str(settings.rerank_threshold),
    }


def _one_retrieval(email: str, question: str) -> float:
    db = SessionLocal()
    try:
        user_row = db.query(User).filter(User.email == email).first()
        if user_row is None:
            raise RuntimeError(f"User {email} not found; run make eval --seed or make demo")
        user = resolve_principal(db, user_row, None)
        if user is None:
            raise RuntimeError(f"User {email} has no membership")
        started = time.perf_counter()
        retrieve(db, user, question)
        return (time.perf_counter() - started) * 1000.0
    finally:
        db.close()


def _run_load(questions: list[tuple[str, str]], *, rounds: int, concurrency: int) -> list[float]:
    tasks = [question for _ in range(rounds) for question in questions]
    latencies: list[float] = []
    if concurrency <= 1:
        for email, question in tasks:
            latencies.append(_one_retrieval(email, question))
        return latencies

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(_one_retrieval, email, question) for email, question in tasks]
        for future in as_completed(futures):
            latencies.append(future.result())
    return latencies


def render_report(
    *,
    email: str,
    stats: dict[str, int | str],
    latencies_ms: list[float],
    rounds: int,
    concurrency: int,
    question_count: int,
    celery_depth: str,
    revision: str,
    dataset_digest: str,
) -> str:
    sorted_ms = sorted(latencies_ms)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total_requests = len(latencies_ms)
    lines = [
        "# Load baseline (retrieval)",
        "",
        f"Generated: `{generated}`",
        f"Code revision: `{revision}`",
        f"Golden dataset SHA-256: `{dataset_digest}`",
        f"Eval user: `{email}` (hybrid `retrieve`: dense + FTS + RRF + rerank, no LLM)",
        "",
        "## Corpus (indexed)",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| `document_chunks` rows | {stats['chunks']} |",
        f"| `documents` ready | {stats['ready_docs']} |",
        f"| `documents` failed | {stats['failed_docs']} |",
        f"| Orgs with chunks | {stats['orgs_with_chunks']} |",
        f"| `HNSW_MAX_SCAN_TUPLES` | {stats['hnsw_max_scan_tuples']} |",
        f"| `HNSW_ITERATIVE_SCAN` | {stats['hnsw_iterative_scan']} |",
        f"| `RERANK_THRESHOLD` | {stats['rerank_threshold']} |",
        "",
        "## Retrieval load",
        "",
        f"- Golden questions: **{question_count}** × **{rounds}** rounds = **{total_requests}** `retrieve()` calls",
        f"- Concurrency: **{concurrency}**",
        f"- Celery queue depth (`LLEN celery`) before run: **{celery_depth}**",
        "",
        "| Latency (ms) | Value |",
        "| --- | ---: |",
        f"| min | {min(sorted_ms):.1f} |",
        f"| mean | {statistics.mean(sorted_ms):.1f} |",
        f"| p50 | {_percentile(sorted_ms, 50):.1f} |",
        f"| p95 | {_percentile(sorted_ms, 95):.1f} |",
        f"| p99 | {_percentile(sorted_ms, 99):.1f} |",
        f"| max | {max(sorted_ms):.1f} |",
        "",
        "## How to reproduce",
        "",
        "```bash",
        "make up-fast",
        "make eval-retrieval   # or existing indexed pilot corpus",
        "make load-baseline    # LOAD_ROUNDS=3 LOAD_CONCURRENCY=2",
        "```",
        "",
        "Pilot acceptance: compare p95 to prior run on the **same** corpus size; if dense weakens in `/inspect`,",
        "raise `HNSW_MAX_SCAN_TUPLES` and re-run. Chat TTFT adds LLM stream time — use `rag_audit_logs` after",
        "a chat soak (`make check-pilot-alerts`).",
        "",
    ]
    return "\n".join(lines) + "\n"


def _celery_depth() -> str:
    try:
        import redis

        client = redis.from_url(get_settings().redis_url, decode_responses=True)
        return str(int(client.llen("celery")))
    except Exception:
        return "n/a"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieval load baseline (no LLM)")
    parser.add_argument("--dataset", type=Path, default=default_dataset_path())
    parser.add_argument("--report", type=Path, default=default_report_path())
    parser.add_argument("--email", default="", help="Override the no-department employee evaluator email")
    parser.add_argument("--rounds", type=int, default=int(os.environ.get("LOAD_ROUNDS", "2")))
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("LOAD_CONCURRENCY", "1")))
    parser.add_argument("--warmup", type=int, default=3)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    dataset = load_golden_dataset(args.dataset)
    email = (args.email or os.environ.get("EVAL_USER_EMAIL") or dataset.eval_user_email).strip()
    questions = [
        (case.eval_user_email or email, case.question) for case in dataset.items if case.kind == "positive"
    ]
    if not questions:
        logger.error("No positive questions in dataset")
        return 2

    db = SessionLocal()
    try:
        corpus = _corpus_stats(db)
    finally:
        db.close()

    if int(corpus["chunks"]) == 0:
        logger.error("No chunks indexed; run make eval-retrieval --seed or index pilot corpus first")
        return 2

    logger.info("Warmup %s queries", args.warmup)
    for case_email, question in questions[: args.warmup]:
        _one_retrieval(case_email, question)

    depth = _celery_depth()
    logger.info(
        "Load: %s questions × %s rounds, concurrency=%s (chunks=%s)",
        len(questions),
        args.rounds,
        args.concurrency,
        corpus["chunks"],
    )
    latencies = _run_load(questions, rounds=args.rounds, concurrency=max(1, args.concurrency))

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        render_report(
            email=", ".join(sorted({case_email for case_email, _ in questions})),
            stats=corpus,
            latencies_ms=latencies,
            rounds=args.rounds,
            concurrency=max(1, args.concurrency),
            question_count=len(questions),
            celery_depth=depth,
            revision=code_revision(),
            dataset_digest=dataset_sha256(args.dataset),
        ),
        encoding="utf-8",
    )
    p95 = _percentile(sorted(latencies), 95)
    logger.info("Wrote %s (p95=%.1f ms, n=%s)", args.report, p95, len(latencies))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
