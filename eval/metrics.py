"""Ragas-style Faithfulness, Context Precision, and Answer Relevance.

Uses the same OpenAI client as chat (no LangChain). Answer Relevance uses a
fixed language-matched encoder so retrieval profile changes do not change the
English regression metric.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass, field

from app.services.ingestion.embeddings import embed_texts_for_profile
from app.services.chat.llm import complete_openai
from app.services.retrieval import NO_CONTEXT_ANSWER
from citation_metrics import citation_support_rate

logger = logging.getLogger(__name__)

JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
JUDGE_JSON_ATTEMPTS = 2


class EvalJudgeError(RuntimeError):
    """A judge failed to return a usable JSON object after retry."""


@dataclass
class RagasScores:
    faithfulness: float | None
    context_precision: float | None
    answer_relevance: float | None
    citation_support_rate: float | None = None
    relevance_questions: list[str] = field(default_factory=list, repr=False)


def is_refusal(answer: str) -> bool:
    text = " ".join((answer or "").split())
    return text == NO_CONTEXT_ANSWER or NO_CONTEXT_ANSWER in text


def score_case(
    *,
    question: str,
    answer: str,
    contexts: list[str],
    ground_truth: str,
    include_answer_relevance: bool,
    include_citation_support: bool = True,
    defer_answer_relevance: bool = False,
) -> RagasScores:
    if is_refusal(answer) or not contexts:
        faithfulness = None
    else:
        faithfulness = _faithfulness(question, answer, contexts)

    if not contexts:
        context_precision = None
    else:
        context_precision = _context_precision(question, ground_truth, contexts)

    answer_relevance: float | None
    relevance_questions: list[str] = []
    if not include_answer_relevance:
        answer_relevance = None
    elif is_refusal(answer):
        answer_relevance = 0.0
    elif defer_answer_relevance:
        relevance_questions = _answer_relevance_questions(answer)
        answer_relevance = None if relevance_questions else 0.0
    else:
        answer_relevance = _answer_relevance(question, answer)

    source_support = _citation_support(question, answer, contexts) if include_citation_support else None

    return RagasScores(
        faithfulness=faithfulness,
        context_precision=context_precision,
        answer_relevance=answer_relevance,
        citation_support_rate=source_support,
        relevance_questions=relevance_questions,
    )


def _citation_support(question: str, answer: str, contexts: list[str]) -> float | None:
    if is_refusal(answer) or not contexts:
        return None
    source_block = "\n\n".join(f"[{index}] {context}" for index, context in enumerate(contexts))
    messages = [
        {
            "role": "system",
            "content": (
                "Evaluate whether every factual claim in the answer is supported by at least one numbered source. "
                "Return JSON only: {\"claims\": [{\"claim\": \"short claim\", "
                "\"source_indexes\": [0]}]}. Use an empty source_indexes list for unsupported claims. "
                "Use only source indexes that directly support that claim. If there are no factual claims, return "
                "{\"claims\": []}. First check each source for a direct statement of the claim; a verbatim match "
                "is supported. Do not infer evidence that is not in the sources. Source indexes are zero-based."
            ),
        },
        {
            "role": "user",
            "content": f"Question:\n{question}\n\nSources:\n{source_block}\n\nAnswer:\n{answer}",
        },
    ]
    return citation_support_rate(_complete_json(messages), source_count=len(contexts), sources=contexts)


def _faithfulness(question: str, answer: str, contexts: list[str]) -> float:
    context_block = "\n\n".join(contexts) if contexts else "(no excerpts)"
    messages = [
        {
            "role": "system",
            "content": (
                "You evaluate RAG faithfulness. Extract factual statements from the answer. "
                "For each statement, set supported=true only if it can be inferred from the context. "
                "Reply with JSON only: {\"statements\": [{\"text\": \"...\", \"supported\": true}]}"
            ),
        },
        {
            "role": "user",
            "content": f"Question:\n{question}\n\nContext:\n{context_block}\n\nAnswer:\n{answer}",
        },
    ]
    payload = _complete_json(messages)
    statements = payload.get("statements") if isinstance(payload, dict) else None
    if not isinstance(statements, list) or not statements:
        return 1.0 if not (answer or "").strip() else 0.0
    flags: list[bool] = []
    for item in statements:
        if not isinstance(item, dict):
            continue
        flags.append(bool(item.get("supported")))
    if not flags:
        return 0.0
    return sum(1 for flag in flags if flag) / len(flags)


def _context_precision(question: str, ground_truth: str, contexts: list[str]) -> float:
    numbered = "\n\n".join(f"[{index}] {text}" for index, text in enumerate(contexts, start=1))
    messages = [
        {
            "role": "system",
            "content": (
                "You evaluate RAG context precision. For each numbered context, decide if it is "
                "useful for answering the question given the ground-truth answer. "
                "Reply with JSON only: {\"verdicts\": [{\"index\": 1, \"relevant\": true}]}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\nGround truth:\n{ground_truth}\n\nContexts:\n{numbered}"
            ),
        },
    ]
    payload = _complete_json(messages)
    verdicts = payload.get("verdicts") if isinstance(payload, dict) else None
    relevant_by_index: dict[int, bool] = {}
    if isinstance(verdicts, list):
        for item in verdicts:
            if not isinstance(item, dict):
                continue
            try:
                index = int(item.get("index"))
            except (TypeError, ValueError):
                continue
            relevant_by_index[index] = bool(item.get("relevant"))
    flags = [relevant_by_index.get(index, False) for index in range(1, len(contexts) + 1)]
    return _precision_at_k(flags)


def _precision_at_k(relevance: list[bool]) -> float:
    """Ragas context precision: average of precision@k at each relevant rank."""
    if not relevance:
        return 0.0
    running_relevant = 0
    scores: list[float] = []
    for rank, is_relevant in enumerate(relevance, start=1):
        if is_relevant:
            running_relevant += 1
            scores.append(running_relevant / rank)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _answer_relevance(question: str, answer: str) -> float:
    generated = _answer_relevance_questions(answer)
    return score_answer_relevance_batch([(question, generated)])[0]


def _answer_relevance_questions(answer: str) -> list[str]:
    messages = [
        {
            "role": "system",
            "content": (
                "Generate three questions that the given answer could be responding to. "
                "Reply with JSON only: {\"questions\": [\"...\", \"...\", \"...\"]}"
            ),
        },
        {"role": "user", "content": f"Answer:\n{answer}"},
    ]
    payload = _complete_json(messages)
    generated = payload.get("questions") if isinstance(payload, dict) else None
    return [str(item).strip() for item in generated or [] if str(item).strip()]


def score_answer_relevance_batch(items: list[tuple[str, list[str]]]) -> list[float]:
    """Embed answer-relevance question groups in bounded batches by language profile."""
    scores = [0.0] * len(items)
    grouped: dict[str, list[tuple[int, str, list[str]]]] = {}
    for index, (question, generated_questions) in enumerate(items):
        if not generated_questions:
            continue
        profile = _answer_relevance_profile(question)
        grouped.setdefault(profile, []).append((index, question, generated_questions))

    for profile, cases in grouped.items():
        flat_texts: list[str] = []
        offsets: list[tuple[int, int, int]] = []
        for index, question, generated_questions in cases:
            start = len(flat_texts)
            flat_texts.extend([question, *generated_questions])
            offsets.append((index, start, len(flat_texts)))

        vectors: list[list[float]] = []
        for start in range(0, len(flat_texts), 128):
            vectors.extend(embed_texts_for_profile(flat_texts[start : start + 128], profile))

        for index, start, end in offsets:
            origin = vectors[start]
            similarities = [_cosine(origin, other) for other in vectors[start + 1 : end]]
            scores[index] = sum(similarities) / len(similarities) if similarities else 0.0
    return scores


def _answer_relevance_profile(question: str) -> str:
    """Use the historical encoder for Latin questions and multilingual for Cyrillic."""
    if any("\u0400" <= char <= "\u04ff" for char in question):
        return "multilingual-compact"
    return "current"


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0.0 or norm_r == 0.0:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_l * norm_r)))


def _complete_json(messages: list[dict[str, str]]) -> dict:
    for attempt in range(JUDGE_JSON_ATTEMPTS):
        text, _usage = complete_openai(messages, temperature=0.0)
        parsed = _extract_json(text)
        if isinstance(parsed, dict):
            return parsed
        if attempt < JUDGE_JSON_ATTEMPTS - 1:
            logger.warning("eval judge returned non-JSON; retrying once")
    raise EvalJudgeError("eval judge returned invalid JSON after retry")


def _extract_json(text: str) -> object | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = JSON_OBJECT_RE.search(raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        logger.warning("eval judge returned non-JSON")
        return None
