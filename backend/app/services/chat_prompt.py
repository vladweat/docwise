"""Chat prompts, LLM message assembly, and Redis answer cache."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.models.chat import ChatMessage, ChatMessageRole
from app.schemas.chat import Citation
from app.services.llm_cache import cache_key, redis_get, redis_set
from app.services.retrieval import NO_CONTEXT_ANSWER, RetrievedChunk

HISTORY_MAX_MESSAGES = 8
TITLE_MAX_LEN = 80

SYSTEM_PROMPT = (
    "You are a corporate AI assistant. Answer strictly using the provided document excerpts. "
    "If the excerpts do not contain the answer, reply exactly: "
    f"«{NO_CONTEXT_ANSWER}» "
    "Do not invent facts, numbers, or policies. "
    "Format lists and tables in Markdown. "
    "Every factual statement must cite the source: for PDFs use "
    "[Title.pdf, стр. N]; for Word documents use [Title.docx, раздел: Section Name] "
    "(no page numbers for DOCX). Reply in the same language as the user's question."
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
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Document excerpts:\n{context}"},
    ]
    for row in history:
        role = row.role
        if role not in {ChatMessageRole.user.value, ChatMessageRole.assistant.value}:
            continue
        messages.append({"role": role, "content": row.content})
    messages.append({"role": "user", "content": question})
    return messages


def load_cached_answer(
    question: str,
    allowed_roles: Sequence[str],
    *,
    organization_id: UUID,
    index_generation: int = 0,
) -> ChatResult | None:
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
