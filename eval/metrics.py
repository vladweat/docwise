"""Ragas-style Faithfulness, Context Precision, and Answer Relevance.

Uses the same OpenAI client as chat (no LangChain). Answer Relevance embeds
generated questions with FastEmbed `BAAI/bge-small-en-v1.5`.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass

from app.services.embeddings import embed_texts
from app.services.llm import complete_openai
from app.services.retrieval import NO_CONTEXT_ANSWER

logger = logging.getLogger(__name__)

JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


@dataclass
class RagasScores:
    faithfulness: float | None
    context_precision: float | None
    answer_relevance: float | None


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
) -> RagasScores:
    if is_refusal(answer):
        faithfulness = 1.0
    else:
        faithfulness = _faithfulness(question, answer, contexts)

    if not contexts:
        context_precision = 1.0
    else:
        context_precision = _context_precision(question, ground_truth, contexts)

    answer_relevance: float | None
    if not include_answer_relevance:
        answer_relevance = None
    elif is_refusal(answer):
        answer_relevance = 0.0
    else:
        answer_relevance = _answer_relevance(question, answer)

    return RagasScores(
        faithfulness=faithfulness,
        context_precision=context_precision,
        answer_relevance=answer_relevance,
    )


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
    questions = [str(item).strip() for item in generated or [] if str(item).strip()]
    if not questions:
        return 0.0
    vectors = embed_texts([question, *questions])
    if len(vectors) < 2:
        return 0.0
    origin = vectors[0]
    sims = [_cosine(origin, other) for other in vectors[1:]]
    return sum(sims) / len(sims)


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
    text, _usage = complete_openai(messages, temperature=0.0)
    parsed = _extract_json(text)
    return parsed if isinstance(parsed, dict) else {}


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
