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

from acl import leaked_doc_ids  # noqa: E402
from corpus import CATALOG_BY_ID, DEFAULT_EVAL_EMAIL, EVAL_ACCOUNTS, FOREIGN_ORG_DOC_ID, seed_corpus, seed_external_corpus  # noqa: E402
from concurrency import map_bounded  # noqa: E402
from app.services.ingestion.embedding_profiles import supported_profiles  # noqa: E402
from app.services.ingestion.embeddings import active_embedding_profile, select_evaluation_embedding_profile  # noqa: E402
from dataset import GoldenCase, load_golden_dataset  # noqa: E402
from metrics import RagasScores, is_refusal, score_answer_relevance_batch, score_case  # noqa: E402
from provenance import code_revision, dataset_sha256, evaluation_config  # noqa: E402
from quality_gates import GateResult, all_gates_pass, evaluate_gates  # noqa: E402
from reporting import (  # noqa: E402
    RETRIEVAL_STAGES,
    metric_slices,
    question_language,
    rerank_threshold_case_metrics,
    rerank_threshold_metrics,
    retrieval_stage_metrics,
    stage_target_ranks,
)

from app.core.database import SessionLocal  # noqa: E402
from app.core.principal import Principal  # noqa: E402
from app.core.rls import bind_session_rls  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.chat import build_messages  # noqa: E402
from app.services.chat.prompt import no_context_answer  # noqa: E402
from app.services.chat.llm import LLMUsage, OpenAINotConfiguredError, openai_is_configured, stream_openai  # noqa: E402
from app.services.retrieval import retrieve  # noqa: E402
from app.services.retrieval.reranker import select_evaluation_reranker_profile  # noqa: E402
from app.services.retrieval.types import RetrievedChunk  # noqa: E402
from app.services.org.tenancy import resolve_principal  # noqa: E402

logger = logging.getLogger("eval")


@dataclass
class CaseResult:
    case: GoldenCase
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_pages: list[int]
    contexts: list[str]
    leaks: list[str]
    target_doc_hit: bool | None
    target_page_hit: bool | None
    target_section_hit: bool | None = None
    retrieval_stage_doc_hits: dict[str, bool] = field(default_factory=dict)
    retrieval_stage_ranks: dict[str, int | None] = field(default_factory=dict)
    rerank_threshold_sweep: dict[str, dict[str, int | bool | None]] = field(default_factory=dict)
    ragas: RagasScores | None = None
    error: str | None = None
    no_answer_correct: bool | None = None


@dataclass
class EvalSummary:
    eval_user_email: str
    generated_at: str
    code_revision: str
    dataset_sha256: str
    config: dict[str, str | int | float] = field(default_factory=dict)
    results: list[CaseResult] = field(default_factory=list)
    retrieval_only: bool = False

    @property
    def positives(self) -> list[CaseResult]:
        return [row for row in self.results if row.case.kind == "positive"]

    @property
    def no_answer_cases(self) -> list[CaseResult]:
        return [row for row in self.results if row.case.is_no_answer]

    @property
    def acl_rows(self) -> list[CaseResult]:
        return [row for row in self.results if row.case.is_acl_negative]

    @property
    def leak_count(self) -> int:
        return sum(1 for row in self.results if row.leaks)

    @property
    def leak_total(self) -> int:
        return sum(len(row.leaks) for row in self.results)

    @property
    def error_count(self) -> int:
        return sum(1 for row in self.results if row.error)

    @property
    def target_doc_hit_count(self) -> int:
        return sum(1 for row in self.positives if row.target_doc_hit)


@dataclass
class PreparedCase:
    """Retrieval output ready for generation; contains text only in process memory."""

    result: CaseResult
    chunks: list[RetrievedChunk]


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
    parser.add_argument("--external-corpus", type=Path, help="Index a prepared external DOCX corpus manifest; requires --seed")
    parser.add_argument(
        "--model-profile",
        choices=supported_profiles(),
        default="current",
        help="Select a model profile for an isolated seeded evaluation",
    )
    parser.add_argument("--limit", type=int, default=0, help="Run only the first N cases")
    parser.add_argument(
        "--concurrency",
        type=_positive_int,
        default=os.environ.get("EVAL_CONCURRENCY", "4"),
        help="Maximum concurrent generation/judge cases (default: EVAL_CONCURRENCY or 4)",
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Skip generation and Ragas judges (ACL + page hits still run)",
    )
    parser.add_argument("--email", default="", help="Override the no-department employee evaluator email")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.external_corpus and not args.seed:
        logger.error("--external-corpus requires --seed")
        return 2
    if args.model_profile != "current" and not args.seed:
        logger.error("A non-default model profile requires --seed to prevent mixing vector spaces")
        return 2
    try:
        _select_eval_model_profile(args.model_profile)
    except (RuntimeError, ValueError) as exc:
        logger.error("Could not select evaluation model profile: %s", exc)
        return 2

    dataset = load_golden_dataset(args.dataset)
    email = (args.email or os.environ.get("EVAL_USER_EMAIL") or dataset.eval_user_email or DEFAULT_EVAL_EMAIL).strip()

    if args.seed:
        logger.info("Seeding eval corpus as %s", email)
        seed_corpus(email=email)
        if args.external_corpus:
            logger.info("Indexing prepared external corpus from %s", args.external_corpus)
            seed_external_corpus(args.external_corpus)

    if not args.retrieval_only and not openai_is_configured():
        logger.error("OPENAI_API_KEY is required unless --retrieval-only")
        return 2

    items = list(dataset.items)
    if args.limit and args.limit > 0:
        items = items[: args.limit]

    summary = EvalSummary(
        eval_user_email=email,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        code_revision=code_revision(),
        dataset_sha256=dataset_sha256(args.dataset),
        config={
            **evaluation_config(),
            "eval_concurrency": args.concurrency,
            "eval_limit": args.limit,
        },
        retrieval_only=args.retrieval_only,
    )
    evaluator_accounts = {account.email: account for account in EVAL_ACCOUNTS}
    users: dict[str, Principal] = {}
    prepared_cases: list[PreparedCase] = []
    db = SessionLocal()
    try:
        for case in items:
            case_email = case.eval_user_email or email
            account = evaluator_accounts.get(case_email)
            if case.eval_user_email is not None:
                if account is None:
                    logger.error("Unknown eval persona %s in case %s", case_email, case.id)
                    return 2
                expected_departments = account.departments
            else:
                expected_departments = ()
            user = users.get(case_email)
            if user is None:
                user_row = db.query(User).filter(User.email == case_email).first()
                if user_row is None or not user_row.is_active:
                    logger.error("Eval user %s is missing; run with --seed", case_email)
                    return 2
                user = resolve_principal(db, user_row, None)
                if user is None:
                    logger.error("Eval user %s has no organization membership; run with --seed", case_email)
                    return 2
                actual_departments = tuple(sorted(user.departments or ()))
                if actual_departments != tuple(sorted(expected_departments)):
                    logger.error(
                        "Eval user %s has departments %s; expected fixture departments %s",
                        case_email,
                        actual_departments,
                        expected_departments,
                    )
                    return 2
                users[case_email] = user
            prepared_cases.append(_prepare_case(db, user, case))
    finally:
        db.close()

    if args.retrieval_only:
        summary.results = [_retrieval_only_result(item) for item in prepared_cases]
    else:
        logger.info(
            "Running generation and judges for %s cases (concurrency=%s)",
            len(prepared_cases),
            args.concurrency,
        )

        completed = 0

        def log_completion(_index: int, _prepared: PreparedCase, result: CaseResult) -> None:
            nonlocal completed
            completed += 1
            status = " (case error)" if result.error else ""
            logger.info(
                "Finished generation/judges %s/%s: %s%s",
                completed,
                len(prepared_cases),
                result.case.id,
                status,
            )

        summary.results = map_bounded(
            prepared_cases,
            _evaluate_prepared_case,
            max_workers=args.concurrency,
            on_complete=log_completion,
        )
        _finish_answer_relevance_batches(summary.results)
        logger.info("Finished batched answer-relevance embeddings")

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
    gates = _quality_gates(summary)
    if not all_gates_pass(gates):
        failed = ", ".join(gate.name for gate in gates if gate.status == "FAIL")
        logger.error("Eval quality gates failed: %s", failed)
        return 1
    return 0


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _run_case(db, user: User, case: GoldenCase, *, retrieval_only: bool) -> CaseResult:
    prepared = _prepare_case(db, user, case)
    if retrieval_only:
        return _retrieval_only_result(prepared)
    result = _evaluate_prepared_case(prepared)
    _finish_answer_relevance_batches([result])
    return result


def _prepare_case(db, user: User, case: GoldenCase) -> PreparedCase:
    bind_session_rls(db, organization_id=user.organization_id)
    retrieval = retrieve(db, user, case.question)
    chunks = list(retrieval.chunks)
    retrieved_doc_ids = [str(chunk.document_id) for chunk in chunks]
    retrieved_pages = [chunk.page_number for chunk in chunks]
    leaks = leaked_doc_ids(retrieved_doc_ids, list(case.must_not_doc_ids) + [str(FOREIGN_ORG_DOC_ID)])
    target = str(case.target_doc_id) if case.target_doc_id is not None else None
    target_doc_hit = target in retrieved_doc_ids if target is not None else None
    target_page_hit: bool | None
    if case.target_page is None or target is None:
        target_page_hit = None
    else:
        target_page_hit = any(
            str(chunk.document_id) == target and chunk.page_number == case.target_page for chunk in chunks
        )
    target_section_hit = (
        any(str(chunk.document_id) == target and chunk.section_title == case.target_section for chunk in chunks)
        if case.target_section is not None and target is not None
        else None
    )
    retrieval_stage_doc_hits = {
        stage: target is not None and any(str(hit.document_id) == target for hit in getattr(retrieval, stage, ()))
        for stage in RETRIEVAL_STAGES
    }
    retrieval_stage_ranks = stage_target_ranks(
        retrieval,
        target_doc_id=target or "",
        target_section=case.target_section,
    )
    rerank_threshold_sweep = (
        rerank_threshold_case_metrics(
            getattr(retrieval, "rerank_scored", ()),
            target_doc_id=target,
            target_section=case.target_section,
        )
        if target is not None
        else {}
    )

    if leaks:
        contexts = ["[redacted restricted chunk]" for _ in chunks]
    else:
        contexts = [chunk.content for chunk in chunks]

    result = CaseResult(
        case=case,
        answer="",
        retrieved_doc_ids=retrieved_doc_ids,
        retrieved_pages=retrieved_pages,
        contexts=contexts,
        leaks=leaks,
        target_doc_hit=target_doc_hit,
        target_page_hit=target_page_hit,
        target_section_hit=target_section_hit,
        retrieval_stage_doc_hits=retrieval_stage_doc_hits,
        retrieval_stage_ranks=retrieval_stage_ranks,
        rerank_threshold_sweep=rerank_threshold_sweep,
    )
    return PreparedCase(result=result, chunks=chunks)


def _retrieval_only_result(prepared: PreparedCase) -> CaseResult:
    prepared.result.answer = no_context_answer(prepared.result.case.question) if not prepared.chunks else ""
    prepared.result.no_answer_correct = None
    return prepared.result


def _evaluate_prepared_case(prepared: PreparedCase) -> CaseResult:
    result = prepared.result
    answer = ""
    try:
        # A retrieval ACL regression must not expose restricted text to a prompt.
        allowed_chunks = [] if result.leaks else prepared.chunks
        answer = _generate(result.case.question, allowed_chunks)
        if result.case.is_no_answer:
            result.no_answer_correct = is_refusal(answer)
        else:
            result.ragas = score_case(
                question=result.case.question,
                answer=answer,
                contexts=[] if result.leaks else result.contexts,
                ground_truth=result.case.ground_truth_answer,
                include_answer_relevance=not result.case.is_acl_negative,
                include_citation_support=not result.case.is_acl_negative,
                defer_answer_relevance=True,
            )
    except OpenAINotConfiguredError:
        raise
    except Exception as exc:
        logger.exception("case %s failed", result.case.id)
        result.error = str(exc)
    result.answer = answer
    return result


def _finish_answer_relevance_batches(results: list[CaseResult]) -> None:
    pending = [
        row for row in results if row.ragas is not None and row.ragas.relevance_questions
    ]
    for start in range(0, len(pending), 32):
        batch = pending[start : start + 32]
        try:
            scores = score_answer_relevance_batch(
                [(row.case.question, row.ragas.relevance_questions) for row in batch if row.ragas is not None]
            )
        except Exception as exc:
            logger.exception("answer relevance embedding batch failed for %s cases", len(batch))
            for row in batch:
                row.error = str(exc)
                if row.ragas is not None:
                    row.ragas.relevance_questions.clear()
            continue

        for row, score in zip(batch, scores, strict=True):
            if row.ragas is not None:
                row.ragas.answer_relevance = score
                row.ragas.relevance_questions.clear()


def _select_eval_model_profile(key: str) -> None:
    select_evaluation_embedding_profile(key)
    select_evaluation_reranker_profile(key)
    profile = active_embedding_profile()
    from app.services.ingestion import chunker

    chunker.CHUNK_MAX_TOKENS = profile.eval_chunk_max_tokens
    chunker.CHUNK_MIN_TOKENS = profile.eval_chunk_min_tokens
    chunker.CHUNK_OVERLAP_TOKENS = profile.eval_chunk_overlap_tokens


def _generate(question: str, chunks) -> str:
    if not chunks:
        return no_context_answer(question)
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


def _quality_gates(summary: EvalSummary) -> list[GateResult]:
    positives = summary.positives
    page_hits = [row.target_page_hit for row in positives if row.target_page_hit is not None]
    english_positives = [row for row in positives if question_language(row.case.question) == "en"]
    return evaluate_gates(
        leaks=summary.leak_count,
        errors=summary.error_count,
        target_doc_hit_rate=_avg([float(row.target_doc_hit) for row in positives]),
        target_page_hit_rate=_avg([float(hit) for hit in page_hits]),
        faithfulness=_avg([row.ragas.faithfulness if row.ragas else None for row in positives]),
        context_precision=_avg([row.ragas.context_precision if row.ragas else None for row in positives]),
        answer_relevance=_avg([row.ragas.answer_relevance if row.ragas else None for row in english_positives]),
        no_answer_refusal_rate=_avg(
            [float(row.no_answer_correct) for row in summary.no_answer_cases if row.no_answer_correct is not None]
        ),
        retrieval_only=summary.retrieval_only,
    )


def _fmt_gate_value(value: int | float | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return _fmt(value)


def render_report(summary: EvalSummary) -> str:
    positives = summary.positives
    no_answer_rows = summary.no_answer_cases
    acl_rows = summary.acl_rows
    faith = _avg([row.ragas.faithfulness if row.ragas else None for row in positives])
    precision = _avg([row.ragas.context_precision if row.ragas else None for row in positives])
    relevance = _avg([row.ragas.answer_relevance if row.ragas else None for row in positives])
    citation_scores = [
        row.ragas.citation_support_rate
        for row in positives
        if row.ragas is not None and row.ragas.citation_support_rate is not None
    ]
    doc_hits = [row.target_doc_hit for row in positives]
    page_hits = [row.target_page_hit for row in positives if row.target_page_hit is not None]
    section_hits = [row.target_section_hit for row in positives if row.target_section_hit is not None]
    quality_gates = _quality_gates(summary)
    if summary.retrieval_only:
        mode = "retrieval-only (Ragas judges skipped)"
    else:
        mode = "retrieval + generation + Ragas judges"

    lines = [
        "# RAG benchmark",
        "",
        f"Generated: `{summary.generated_at}`",
        f"Code revision: `{summary.code_revision}`",
        f"Golden dataset SHA-256: `{summary.dataset_sha256}`",
        "Run configuration (safe fields only):",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(summary.config.items()))
    lines.extend([
        "Eval personas: `employee`, `hr`, `finance`, `legal`, `security`, `engineering`",
        f"Cases: {len(summary.results)} ({len(positives)} positive, {len(no_answer_rows)} no-answer, {len(acl_rows)} ACL-negative)",
        f"Case errors: {summary.error_count}",
        f"Pipeline: hybrid `retrieve` → Top-4 → `build_messages` + `stream_openai` ({mode})",
        "",
        "Metrics follow Ragas definitions (Faithfulness, Context Precision, Answer Relevance) "
        "using the same OpenAI-compatible client as chat. Answer Relevance uses a fixed encoder per script: "
        "the historical BGE encoder for Latin questions and multilingual MiniLM for Cyrillic questions; "
        "the regression gate uses only the English slice. LangChain is not used.",
        "",
        "## Ragas (positive cases)",
        "",
        "| Metric | Score | n |",
        "| --- | ---: | ---: |",
        f"| Faithfulness | {_fmt(faith)} | {sum(row.ragas is not None and row.ragas.faithfulness is not None for row in positives)} |",
        f"| Context Precision | {_fmt(precision)} | {sum(row.ragas is not None and row.ragas.context_precision is not None for row in positives)} |",
        f"| Answer Relevance | {_fmt(relevance)} | {sum(row.ragas is not None and row.ragas.answer_relevance is not None for row in positives)} |",
        f"| Citation support | {_fmt(_avg(citation_scores))} | {len(citation_scores)} |",
        "",
        "## Response coverage",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ])
    if summary.retrieval_only:
        lines.extend(
            [
                "| Answers | n/a (retrieval-only) |",
                "| Refusals | n/a (retrieval-only) |",
                "| Cases with context | n/a (retrieval-only) |",
                "| Correct no-answer refusals | n/a (retrieval-only) |",
                "| False no-answer answers | n/a (retrieval-only) |",
            ]
        )
    else:
        answered = sum(bool(row.answer.strip()) and not is_refusal(row.answer) for row in positives)
        refusals = sum(is_refusal(row.answer) for row in positives)
        with_context = sum(bool(row.contexts) for row in positives)
        lines.extend(
            [
                f"| Answers | {answered} / {len(positives)} |",
                f"| Refusals | {refusals} / {len(positives)} |",
                f"| Cases with context | {with_context} / {len(positives)} |",
                f"| Correct no-answer refusals | {sum(row.no_answer_correct is True for row in no_answer_rows)} / {len(no_answer_rows)} |",
                f"| False no-answer answers | {sum(row.no_answer_correct is False for row in no_answer_rows)} / {len(no_answer_rows)} |",
            ]
        )
    lines.extend(["", "## No-answer behavior", ""])
    lines.extend(
        [
            "No-answer questions are evaluated separately from answerable retrieval and ACL cases.",
            "",
            "| Metric | Value |",
            "| --- | ---: |",
            f"| Cases | {len(no_answer_rows)} |",
            (
                f"| Correct refusal rate | {_fmt(_avg([float(row.no_answer_correct) for row in no_answer_rows if row.no_answer_correct is not None]))} |"
                if not summary.retrieval_only
                else "| Correct refusal rate | n/a (retrieval-only) |"
            ),
            "",
        ]
    )
    lines.extend([
        "",
        "## Retrieval",
        "",
        "| Metric | Score | n |",
        "| --- | ---: | ---: |",
        f"| Target document hit rate | {_fmt(mean(doc_hits) if doc_hits else None)} | {len(doc_hits)} |",
        f"| Target page hit rate | {_fmt(mean(page_hits) if page_hits else None)} | {len(page_hits)} |",
        f"| Target section hit rate | {_fmt(mean(section_hits) if section_hits else None)} | {len(section_hits)} |",
        "",
        "## Retrieval stage diagnostics",
        "",
        "Stage lists are evaluated only for target presence/rank; snippets, answers, and passage text are not emitted.",
        "",
    ])
    datasets = sorted({row.case.source_dataset for row in positives})
    for source_dataset in datasets:
        selected = [row for row in positives if row.case.source_dataset == source_dataset]
        stage_rows = retrieval_stage_metrics(selected)
        lines.extend(
            [
                f"### {source_dataset}",
                "",
                "| Stage | Cases | Section cases | Target doc hit | Exact section Recall@1 | Recall@4 | Recall@10 | MRR |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for stage in stage_rows:
            lines.append(
                "| {stage} | {cases} | {section_cases} | {doc_hit} | {r1} | {r4} | {r10} | {mrr} |".format(
                    stage=stage["stage"],
                    cases=stage["cases"],
                    section_cases=stage["section_cases"],
                    doc_hit=_fmt(stage["target_doc_hit_rate"]),
                    r1=_fmt(stage["section_recall_at_1"]),
                    r4=_fmt(stage["section_recall_at_4"]),
                    r10=_fmt(stage["section_recall_at_10"]),
                    mrr=_fmt(stage["section_mrr"]),
                )
            )
        lines.append("")
        lines.extend(
            [
                "Threshold simulation from the same reranker scores (no extra inference):",
                "",
                "| Threshold | Target doc hit | Section Recall@1 | Section Recall@4 | Section MRR | Mean returned | Empty rate |",
                "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for threshold_row in rerank_threshold_metrics(selected):
            lines.append(
                "| {threshold} | {doc} | {r1} | {r4} | {mrr} | {returned} | {empty} |".format(
                    threshold=threshold_row["threshold"],
                    doc=_fmt(threshold_row["target_doc_hit_rate"]),
                    r1=_fmt(threshold_row["section_recall_at_1"]),
                    r4=_fmt(threshold_row["section_recall_at_4"]),
                    mrr=_fmt(threshold_row["section_mrr"]),
                    returned=_fmt(threshold_row["mean_returned"]),
                    empty=_fmt(threshold_row["empty_rate"]),
                )
            )
        lines.append("")
    lines.extend([
        "## Quality gates",
        "",
        "Initial regression floors are based on the full run dated 2026-10-30; they are not statistical confidence bounds.",
        "",
        "| Gate | Observed | Threshold | Status |",
        "| --- | ---: | ---: | --- |",
    ])
    lines.extend(
        f"| {gate.name} | {_fmt_gate_value(gate.observed)} | {gate.threshold} | {gate.status} |"
        for gate in quality_gates
    )
    lines.extend([
        "",
        "Generation quality was not evaluated in this retrieval-only run." if summary.retrieval_only else "",
        "",
        "## Quality slices (positive cases)",
        "",
    ])
    for dimension in ("language", "persona", "kind", "source_dataset"):
        lines.extend(
            [
                f"### By {dimension}",
                "",
                "| Group | Cases | Doc hit | Page hit | Section hit | Faithfulness | Context precision | Answer relevance | Citation support | Errors |",
                "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in metric_slices(summary.results, dimension, default_persona=summary.eval_user_email):
            lines.append(
                "| {label} | {cases} | {doc} | {page} | {section} | {faith} | {context} | {relevance} | {citation} | {errors} |".format(
                    label=row["label"],
                    cases=row["cases"],
                    doc=_fmt(row["doc_hit_rate"]),
                    page=_fmt(row["page_hit_rate"]),
                    section=_fmt(row["section_hit_rate"]),
                    faith=_fmt(row["faithfulness"]),
                    context=_fmt(row["context_precision"]),
                    relevance=_fmt(row["answer_relevance"]),
                    citation=_fmt(row["citation_support_rate"]),
                    errors=row["errors"],
                )
            )
        lines.append("")
    lines.extend([
        "## ACL negatives",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Cases | {len(acl_rows)} |",
        f"| Cases with a `must_not_doc_ids` leak | **{summary.leak_count}** |",
        f"| Result | {'PASS' if summary.leak_count == 0 else 'FAIL'} |",
        "",
        "Each case lists documents outside that persona's access in `must_not_doc_ids`. "
        "A leak is any Top-4 chunk from those documents. Restricted chunk text is not written here.",
        "",
        "## Per-question",
        "",
        "| id | persona | kind | target doc | page hit | section hit | ACL leak | faith | ctx p | ans rel | citation support | question |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in summary.results:
        ragas = row.ragas
        page = "n/a"
        if row.target_page_hit is True:
            page = "hit"
        elif row.target_page_hit is False:
            page = "miss"
        section = "n/a"
        if row.target_section_hit is True:
            section = "hit"
        elif row.target_section_hit is False:
            section = "miss"
        slug = CATALOG_BY_ID.get(row.case.target_doc_id)
        target = slug.slug if slug else (row.case.target_doc_id[:8] if row.case.target_doc_id else "—")
        leak = ",".join(row.leaks) if row.leaks else "0"
        question = row.case.question.replace("|", "/")
        persona = row.case.eval_user_email or summary.eval_user_email
        lines.append(
            "| {id} | {persona} | {kind} | {target} | {page} | {section} | {leak} | {faith} | {ctx} | {rel} | {citation} | {q} |".format(
                id=row.case.id,
                persona=persona,
                kind=row.case.kind,
                target=target,
                page=page,
                section=section,
                leak=leak,
                faith=_fmt(ragas.faithfulness if ragas else None),
                ctx=_fmt(ragas.context_precision if ragas else None),
                rel=_fmt(ragas.answer_relevance if ragas else None),
                citation=_fmt(ragas.citation_support_rate if ragas else None),
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
