#!/usr/bin/env python3
"""Run real retrieval+generation under the eval employee's RBAC and write Ragas metrics.

Not invoked by default CI: needs an LLM key and indexed fixture documents.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
if BACKEND_DIR.is_dir():
    sys.path.insert(0, str(BACKEND_DIR))
elif Path("/app/app").is_dir():
    sys.path.insert(0, "/app")
sys.path.insert(0, str(EVAL_DIR))

from acl import leaked_doc_ids
from corpus import CATALOG_BY_ID, DEFAULT_EVAL_EMAIL, FOREIGN_ORG_DOC_ID, seed_corpus
from dataset import GoldenCase, load_golden_dataset
from metrics import RagasScores, score_case

from app.core.database import SessionLocal
from app.models.user import User
from app.services.chat import build_messages
from app.services.llm import LLMUsage, OpenAINotConfiguredError, openai_is_configured, stream_openai
from app.services.retrieval import NO_CONTEXT_ANSWER, retrieve
from app.services.tenancy import resolve_principal

logger = logging.getLogger("eval")

REFUSAL = NO_CONTEXT_ANSWER
FAITHFULNESS_GATE = 0.8


@dataclass
class CaseResult:
    case: GoldenCase
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_pages: list[int]
    contexts: list[str]
    leaks: list[str]
    target_doc_hit: bool
    target_page_hit: bool | None
    ragas: RagasScores | None = None
    error: str | None = None


@dataclass
class EvalSummary:
    eval_user_email: str
    generated_at: str
    results: list[CaseResult] = field(default_factory=list)
    retrieval_only: bool = False

    @property
    def positives(self) -> list[CaseResult]:
        return [row for row in self.results if not row.case.is_acl_negative]

    @property
    def acl_rows(self) -> list[CaseResult]:
        return [row for row in self.results if row.case.is_acl_negative]

    @property
    def leak_count(self) -> int:
        return sum(1 for row in self.results if row.leaks)

    @property
    def leak_total(self) -> int:
        return sum(len(row.leaks) for row in self.results)


def default_report_path() -> Path:
    env = os.environ.get("EVAL_REPORT")
    if env:
        return Path(env)
    if (REPO_ROOT / "docs").is_dir():
        return REPO_ROOT / "reports" / "rag_benchmark.md"
    return Path("/reports/rag_benchmark.md")


def default_dataset_path() -> Path:
    env = os.environ.get("EVAL_DATASET")
    if env:
        return Path(env)
    return EVAL_DIR / "golden_dataset.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Docwise RAG eval (real retrieval + generation)")
    parser.add_argument("--dataset", type=Path, default=default_dataset_path())
    parser.add_argument("--report", type=Path, default=default_report_path())
    parser.add_argument("--seed", action="store_true", help="Index fixture PDFs and ensure the eval user")
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N cases")
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Skip generation and Ragas judges (ACL + page hits still run)",
    )
    parser.add_argument("--email", default="", help="Override eval user email")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    dataset = load_golden_dataset(args.dataset)
    email = (args.email or os.environ.get("EVAL_USER_EMAIL") or dataset.eval_user_email or DEFAULT_EVAL_EMAIL).strip()

    if args.seed:
        logger.info("Seeding eval corpus as %s", email)
        seed_corpus(email=email)

    if not args.retrieval_only and not openai_is_configured():
        logger.error("OPENAI_API_KEY is required unless --retrieval-only")
        return 2

    items = list(dataset.items)
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    summary = EvalSummary(
        eval_user_email=email,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        retrieval_only=args.retrieval_only,
    )
    db = SessionLocal()
    try:
        user_row = db.query(User).filter(User.email == email).first()
        if user_row is None or not user_row.is_active:
            logger.error("Eval user %s is missing; run with --seed", email)
            return 2
        user = resolve_principal(db, user_row, None)
        if user is None:
            logger.error("Eval user %s has no organization membership; run with --seed", email)
            return 2
        allowed = set(user.allowed_roles())
        if "hr" in allowed or "finance" in allowed:
            logger.error(
                "Eval user %s has extra departments %s; employee with no departments is required",
                email,
                user.departments,
            )
            return 2
        for case in items:
            summary.results.append(_run_case(db, user, case, retrieval_only=args.retrieval_only))
    finally:
        db.close()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_report(summary), encoding="utf-8")
    logger.info("Wrote %s", args.report)

    leaks = summary.leak_count
    logger.info(
        "ACL leaks: %s cases / %s docs; positives=%s negatives=%s",
        leaks,
        summary.leak_total,
        len(summary.positives),
        len(summary.acl_rows),
    )
    if leaks:
        logger.error("ACL leak gate failed")
        return 1
    return 0


def _run_case(db, user: User, case: GoldenCase, *, retrieval_only: bool) -> CaseResult:
    retrieval = retrieve(db, user, case.question)
    chunks = list(retrieval.chunks)
    retrieved_doc_ids = [str(chunk.document_id) for chunk in chunks]
    retrieved_pages = [chunk.page_number for chunk in chunks]
    leaks = leaked_doc_ids(retrieved_doc_ids, list(case.must_not_doc_ids) + [str(FOREIGN_ORG_DOC_ID)])
    target = str(case.target_doc_id)
    target_doc_hit = target in retrieved_doc_ids
    target_page_hit: bool | None
    if case.target_page is None:
        target_page_hit = None
    else:
        target_page_hit = any(
            str(chunk.document_id) == target and chunk.page_number == case.target_page for chunk in chunks
        )

    if leaks:
        contexts = ["[redacted restricted chunk]" for _ in chunks]
    else:
        contexts = [chunk.content for chunk in chunks]

    answer = ""
    error = None
    ragas: RagasScores | None = None
    if retrieval_only:
        answer = REFUSAL if not chunks else ""
    else:
        try:
            answer = _generate(case.question, chunks)
            ragas = score_case(
                question=case.question,
                answer=answer,
                contexts=[] if leaks else contexts,
                ground_truth=case.ground_truth_answer,
                include_answer_relevance=not case.is_acl_negative,
            )
        except OpenAINotConfiguredError:
            raise
        except Exception as exc:
            logger.exception("case %s failed", case.id)
            error = str(exc)
            answer = answer or ""

    return CaseResult(
        case=case,
        answer=answer,
        retrieved_doc_ids=retrieved_doc_ids,
        retrieved_pages=retrieved_pages,
        contexts=contexts,
        leaks=leaks,
        target_doc_hit=target_doc_hit,
        target_page_hit=target_page_hit,
        ragas=ragas,
        error=error,
    )


def _generate(question: str, chunks) -> str:
    if not chunks:
        return REFUSAL
    messages = build_messages(question, chunks, history=())
    parts: list[str] = []
    for item in stream_openai(messages):
        if isinstance(item, LLMUsage):
            continue
        parts.append(item)
    return "".join(parts)


def _avg(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return mean(present)


def _fmt(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def render_report(summary: EvalSummary) -> str:
    positives = summary.positives
    acl_rows = summary.acl_rows
    faith = _avg([row.ragas.faithfulness if row.ragas else None for row in positives])
    precision = _avg([row.ragas.context_precision if row.ragas else None for row in positives])
    relevance = _avg([row.ragas.answer_relevance if row.ragas else None for row in positives])
    doc_hits = [row.target_doc_hit for row in positives]
    page_hits = [row.target_page_hit for row in positives if row.target_page_hit is not None]
    leak_pass = summary.leak_count == 0
    if summary.retrieval_only:
        mode = "retrieval-only (Ragas judges skipped)"
    else:
        mode = "retrieval + generation + Ragas judges"

    lines = [
        "# RAG benchmark",
        "",
        f"Generated: `{summary.generated_at}`",
        f"Eval user: `{summary.eval_user_email}` (role `employee`, departments `[]`)",
        f"Cases: {len(summary.results)} ({len(positives)} positive, {len(acl_rows)} ACL-negative)",
        f"Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` ({mode})",
        "",
        "Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) "
        "using the same OpenAI-compatible client as chat. LangChain is not used.",
        "",
        "## Ragas (positive cases)",
        "",
        "| Metric | Score | n |",
        "| --- | ---: | ---: |",
        f"| Faithfulness | {_fmt(faith)} | {len(positives)} |",
        f"| Context Precision | {_fmt(precision)} | {len(positives)} |",
        f"| Answer Relevance | {_fmt(relevance)} | {len(positives)} |",
        "",
        f"Release gate (preliminary): Faithfulness ≥ {FAITHFULNESS_GATE:.1f} on the golden set.",
        "",
        "## Retrieval",
        "",
        "| Metric | Score | n |",
        "| --- | ---: | ---: |",
        f"| Target document hit rate | {_fmt(mean(doc_hits) if doc_hits else None)} | {len(doc_hits)} |",
        f"| Target page hit rate | {_fmt(mean(page_hits) if page_hits else None)} | {len(page_hits)} |",
        "",
        "## ACL negatives",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Cases | {len(acl_rows)} |",
        f"| Cases with a `must_not_doc_ids` leak | **{summary.leak_count}** |",
        f"| Result | {'PASS' if leak_pass else 'FAIL'} |",
        "",
        "Every golden item also lists HR/Finance ids in `must_not_doc_ids`. "
        "A leak is any Top-4 chunk from those documents. Restricted chunk text is not written here.",
        "",
        "## Per-question",
        "",
        "| id | kind | target doc | page | ACL leak | faith | ctx p | ans rel | question |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in summary.results:
        ragas = row.ragas
        page = "n/a"
        if row.target_page_hit is True:
            page = "hit"
        elif row.target_page_hit is False:
            page = "miss"
        slug = CATALOG_BY_ID.get(row.case.target_doc_id)
        target = slug.slug if slug else row.case.target_doc_id[:8]
        leak = ",".join(row.leaks) if row.leaks else "0"
        question = row.case.question.replace("|", "/")
        lines.append(
            "| {id} | {kind} | {target} | {page} | {leak} | {faith} | {ctx} | {rel} | {q} |".format(
                id=row.case.id,
                kind=row.case.kind,
                target=target,
                page=page,
                leak=leak,
                faith=_fmt(ragas.faithfulness if ragas else None),
                ctx=_fmt(ragas.context_precision if ragas else None),
                rel=_fmt(ragas.answer_relevance if ragas else None),
                q=question,
            )
        )
    lines.append("")
    if summary.leak_count:
        lines.extend(
            [
                "## Leaked document ids",
                "",
                "UUIDs only (no titles of hidden files, no chunk text):",
                "",
            ]
        )
        leaked = sorted({doc_id for row in summary.results for doc_id in row.leaks})
        for doc_id in leaked:
            lines.append(f"- `{doc_id}`")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    # ONNX/FastEmbed worker threads otherwise keep the interpreter alive.
    os._exit(main())
