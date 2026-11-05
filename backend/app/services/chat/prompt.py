"""Chat prompts, LLM message assembly, and Redis answer cache."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.models.chat import ChatMessage, ChatMessageRole
from app.schemas.chat import Citation
from app.services.chat.llm_cache import cache_key, redis_get, redis_set
from app.services.retrieval import NO_CONTEXT_ANSWER, RetrievedChunk

HISTORY_MAX_MESSAGES = 8
TITLE_MAX_LEN = 80

SYSTEM_PROMPT = (
    "You are a corporate AI assistant. Answer strictly using the provided document excerpts. "
    "If the excerpts do not contain the answer, reply exactly with the standard refusal in the "
    "same language as the latest user question. For English, use: "
    "‘The provided documents do not contain information on this question.’ For Russian, use: "
    f"«{NO_CONTEXT_ANSWER}» "
    "Do not invent facts, numbers, or policies. "
    "Format lists and tables in Markdown. "
    "Every factual statement must cite the source: for PDFs use "
    "[Title.pdf, стр. N]; for Word documents use [Title.docx, раздел: Section Name] "
    "(no page numbers for DOCX). Reply in the same language as the user's question."
)

_CYRILLIC_RE = re.compile(r"[\u0400-\u04ff]")
_LATIN_RE = re.compile(r"[a-z]", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z]+", re.IGNORECASE)
_QUOTED_TEXT_RE = re.compile(r"«[^»]*»|“[^”]*”|‘[^’]*’")
_ENGLISH_HINTS = frozenset(
    {
        "a",
        "about",
        "and",
        "are",
        "can",
        "compare",
        "could",
        "do",
        "does",
        "explain",
        "find",
        "for",
        "give",
        "how",
        "is",
        "list",
        "me",
        "may",
        "my",
        "of",
        "please",
        "show",
        "tell",
        "the",
        "this",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "would",
        "you",
    }
)

NO_CONTEXT_ANSWER_EN = "The provided documents do not contain information on this question."


def _latest_question_language(question: str) -> str | None:
    language_sample = _QUOTED_TEXT_RE.sub(" ", question)
    cyrillic_count = len(_CYRILLIC_RE.findall(language_sample))
    latin_count = len(_LATIN_RE.findall(language_sample))
    if cyrillic_count > 0 and cyrillic_count >= latin_count:
        return "Russian"
    elif latin_count > 0 and set(_WORD_RE.findall(language_sample.lower())) & _ENGLISH_HINTS:
        return "English"
    return None


def no_context_answer(question: str) -> str:
    """Return the standard no-context response in the latest question's language."""
    if _latest_question_language(question) == "English":
        return NO_CONTEXT_ANSWER_EN
    return NO_CONTEXT_ANSWER


def is_no_context_answer(answer: str) -> bool:
    """Recognize a complete standard refusal, optionally preceded by an answer label."""
    normalized = _normalize_refusal_text(answer)
    return normalized in {_normalize_refusal_text(text) for text in _no_context_answers()}


def contains_no_context_phrase(answer: str) -> bool:
    """Return whether an answer contains a standard refusal phrase anywhere."""
    normalized = " ".join((answer or "").split()).casefold()
    return any(refusal.casefold() in normalized for refusal in _no_context_answers())


def _no_context_answers() -> tuple[str, str]:
    return NO_CONTEXT_ANSWER, NO_CONTEXT_ANSWER_EN


def _normalize_refusal_text(answer: str) -> str:
    normalized = " ".join((answer or "").split()).casefold().strip()
    for prefix in ("answer:", "ответ:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].lstrip()
            break
    normalized = normalized.strip(" \t\r\n\"'`“”‘’«»*_ ")
    return normalized.rstrip(".!?。！？… ").strip()


def _latest_question_language_instruction(question: str) -> str:
    language = _latest_question_language(question)
    if language is None:
        language_rule = "Reply in the same language as the latest user question."
    else:
        language_rule = (
            f"The latest user question is in {language}. Answer in {language}, regardless of "
            "prior conversation or document language."
        )
    return (
        f"{language_rule} Use concise, complete, self-contained sentences. Do not answer with a fragment "
        "or switch to the language used by the document excerpts. Answer the exact question directly "
        "and retain the specific conditions, deadlines, or named systems from the excerpts."
    )


class ChatError(Exception):
    """Raised when chat orchestration fails."""


class ChatPersistError(ChatError):
    """Answer was produced but chat_sessions / messages were not written."""


@dataclass(frozen=True)
class HistoryTurn:
    role: str
    content: str


@dataclass
class ChatResult:
    answer: str
    citations: list[Citation] = field(default_factory=list)
    cached: bool = False
    tokens_used: int | None = None
    cost_usd: Decimal | None = None
    chunk_ids: list[str] = field(default_factory=list)
    session_id: UUID | None = None
    message_id: UUID | None = None


def citations_from_chunks(chunks: Sequence[RetrievedChunk]) -> list[Citation]:
    return [Citation.model_validate(chunk.to_citation()) for chunk in chunks]


def build_messages(
    question: str,
    chunks: Sequence[RetrievedChunk],
    history: Sequence[HistoryTurn | ChatMessage] = (),
) -> list[dict[str, str]]:
    """LLM messages. Context is only the current ACL-filtered Top-4; history is dialogue, not retrieval."""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        title = chunk.doc_title or "Document"
        if chunk.page_number > 0:
            parts.append(f"[{index}] {title} | page {chunk.page_number}\n{chunk.content}")
        else:
            section = (chunk.section_title or "").strip() or "Document"
            parts.append(f"[{index}] {title} | section {section}\n{chunk.content}")
    context = "\n\n".join(parts) if parts else "(no excerpts)"
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n{_latest_question_language_instruction(question)}",
        },
        {"role": "system", "content": f"Document excerpts:\n{context}"},
    ]
    for row in history:
        role = row.role
        if role not in {ChatMessageRole.user.value, ChatMessageRole.assistant.value}:
            continue
        messages.append({"role": role, "content": row.content})
    messages.append({"role": "system", "content": _latest_question_language_instruction(question)})
    messages.append({"role": "user", "content": question})
    return messages


def load_cached_answer(
    question: str,
    allowed_roles: Sequence[str],
    *,
    organization_id: UUID,
    index_generation: int = 0,
) -> ChatResult | None:
    """Return a prior answer only when org, generation, and roles hash match."""
    payload = redis_get(
        cache_key(
            question,
            allowed_roles,
            organization_id=organization_id,
            index_generation=index_generation,
        )
    )
    if payload is None:
        return None
    return _result_from_cache_payload(payload)


def save_cached_answer(
    question: str,
    allowed_roles: Sequence[str],
    result: ChatResult,
    *,
    organization_id: UUID,
    index_generation: int = 0,
) -> None:
    """Store answer under the same scoped key as `load_cached_answer`."""
    redis_set(
        cache_key(
            question,
            allowed_roles,
            organization_id=organization_id,
            index_generation=index_generation,
        ),
        _cache_payload(result),
    )


def title_from_query(query: str) -> str:
    compact = " ".join(query.split())
    if len(compact) <= TITLE_MAX_LEN:
        return compact
    return compact[: TITLE_MAX_LEN - 1].rstrip() + "…"


def _cache_payload(result: ChatResult) -> dict[str, Any]:
    return {
        "answer": result.answer,
        "citations": [citation.model_dump(mode="json") for citation in result.citations],
        "chunk_ids": list(result.chunk_ids),
    }


def _result_from_cache_payload(payload: dict[str, Any]) -> ChatResult:
    citations: list[Citation] = []
    for item in payload.get("citations") or []:
        if not isinstance(item, dict):
            continue
        try:
            citations.append(Citation.model_validate(item))
        except Exception:
            continue
    chunk_ids = [str(item) for item in (payload.get("chunk_ids") or [])]
    return ChatResult(
        answer=str(payload.get("answer") or ""),
        citations=citations,
        cached=True,
        tokens_used=None,
        cost_usd=None,
        chunk_ids=chunk_ids,
    )
