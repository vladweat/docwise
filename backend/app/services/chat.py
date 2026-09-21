"""Permission-aware chat: hybrid retrieval → grounded SSE, Redis cache keyed by allowed_roles."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import NotFoundError
from app.core.time import utcnow_naive
from app.core.sentry import capture_pipeline_error
from app.core.principal import Principal
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.user import User
from app.schemas.chat import Citation
from app.services.audit import record_retrieval_audit
from app.services.chat_sessions import (
    get_owned_session,
    get_session_detail,
    list_sessions,
    set_message_feedback,
)
from app.services.llm import (
    LLMUsage,
    OpenAINotConfiguredError,
    OpenAIRequestError,
    openai_is_configured,
    stream_openai,
)
from app.services.llm_cache import (
    CACHE_VERSION,
    cache_key,
    canonical_allowed_roles,
    question_hash,
    redis_get,
    redis_set,
)
from app.services.quotas import QUOTA_EXCEEDED, has_chat_token_quota, lock_organization
from app.services.retrieval import (
    NO_CONTEXT_ANSWER,
    RetrievedChunk,
    allowed_roles_for,
    embed_query,
    finish_retrieval,
    hybrid_search,
    retrieve as default_retrieve,
)
from app.services.tenancy import resolve_principal

logger = logging.getLogger(__name__)

retrieve = default_retrieve

HISTORY_MAX_MESSAGES = 8
TITLE_MAX_LEN = 80
GENERIC_CHAT_ERROR = "Chat failed. Try again."
PERSIST_FAILED = "Chat was not saved. Try again."

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


def iter_sse_events(
    user_id: UUID,
    query: str,
    session_id: UUID | None,
    *,
    organization_id: UUID,
    retriever=None,
    streamer=None,
) -> Iterator[str]:
    started = time.perf_counter()
    search = retriever if retriever is not None else retrieve
    generate = streamer or stream_openai
    use_split = retriever is None and search is default_retrieve

    try:
        with SessionLocal() as db:
            user = _principal_or_none(db, user_id, organization_id)
            if user is None:
                yield _sse({"type": "error", "content": GENERIC_CHAT_ERROR})
                yield _sse_done()
                return
            if not has_chat_token_quota(db, user.organization):
                yield _sse({"type": "error", "content": QUOTA_EXCEEDED})
                yield _sse_done()
                return

            session = get_owned_session(db, user, session_id) if session_id is not None else None
            allowed = canonical_allowed_roles(allowed_roles_for(user))
            history = _snapshot_history(db, session.id) if session is not None else []
            index_generation = int(user.organization.llm_index_generation or 0)
            cached = load_cached_answer(
                query,
                allowed,
                organization_id=user.organization_id,
                index_generation=index_generation,
            )
            if cached is not None:
                persist_ok = True
                try:
                    persist = _persist_turn(
                        db,
                        user=user,
                        session=session,
                        query=query,
                        result=cached,
                        latency_ms=_elapsed_ms(started),
                    )
                    cached.session_id = persist.session_id
                    cached.message_id = persist.message_id
                except ChatPersistError:
                    persist_ok = False
                yield from _sse_from_result(cached, persist_ok=persist_ok)
                return

        retrieval = _run_retrieval(
            search,
            user_id,
            organization_id,
            query,
            use_split=use_split,
        )
        if retrieval is None:
            yield _sse({"type": "error", "content": GENERIC_CHAT_ERROR})
            yield _sse_done()
            return

        chunks = list(retrieval.chunks)
        citations = citations_from_chunks(chunks)
        if chunks and not openai_is_configured() and streamer is None:
            raise OpenAINotConfiguredError("OPENAI_API_KEY is not configured")

        yield _sse(
            {
                "type": "citations",
                "citations": [citation.model_dump(mode="json") for citation in citations],
            }
        )

        if not chunks:
            result = ChatResult(answer=NO_CONTEXT_ANSWER, citations=[], cached=False, chunk_ids=[])
            result, persist_ok = _persist_closed(
                user_id,
                organization_id,
                session_id,
                query,
                result,
                _elapsed_ms(started),
            )
            save_cached_answer(
                query,
                allowed,
                result,
                organization_id=organization_id,
                index_generation=index_generation,
            )
            yield _sse({"type": "token", "content": result.answer})
            yield from _sse_finish(result, persist_ok=persist_ok)
            return

        messages = build_messages(query, chunks, history)
        parts: list[str] = []
        usage = LLMUsage()
        for item in generate(messages):
            if isinstance(item, LLMUsage):
                usage = item
                continue
            parts.append(item)
            yield _sse({"type": "token", "content": item})

        result = ChatResult(
            answer="".join(parts),
            citations=citations,
            cached=False,
            tokens_used=usage.tokens_used,
            cost_usd=usage.cost_usd,
            chunk_ids=[str(chunk.id) for chunk in chunks],
        )
        result, persist_ok = _persist_closed(
            user_id,
            organization_id,
            session_id,
            query,
            result,
            _elapsed_ms(started),
        )
        save_cached_answer(
            query,
            allowed,
            result,
            organization_id=organization_id,
            index_generation=index_generation,
        )
        yield from _sse_finish(result, persist_ok=persist_ok)
    except ChatPersistError:
        yield _sse({"type": "error", "content": PERSIST_FAILED})
        yield _sse_done()
    except (OpenAINotConfiguredError, OpenAIRequestError, ChatError):
        raise
    except NotFoundError:
        raise
    except Exception as exc:
        capture_pipeline_error("chat", exc)
        logger.exception("Chat stream failed")
        yield _sse({"type": "error", "content": GENERIC_CHAT_ERROR})
        yield _sse_done()


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


def _principal_or_none(db: Session, user_id: UUID, organization_id: UUID) -> Principal | None:
    user_row = db.get(User, user_id)
    if user_row is None or not user_row.is_active:
        return None
    return resolve_principal(db, user_row, organization_id)


def _run_retrieval(search, user_id: UUID, organization_id: UUID, query: str, *, use_split: bool):
    if use_split:
        vector = embed_query(query)
        with SessionLocal() as db:
            user = _principal_or_none(db, user_id, organization_id)
            if user is None:
                return None
            pool = hybrid_search(db, user, query, vector)
        return finish_retrieval(query, pool)

    with SessionLocal() as db:
        user = _principal_or_none(db, user_id, organization_id)
        if user is None:
            return None
        return search(db, user, query)


def _persist_closed(
    user_id: UUID,
    organization_id: UUID,
    session_id: UUID | None,
    query: str,
    result: ChatResult,
    latency_ms: int,
) -> tuple[ChatResult, bool]:
    try:
        with SessionLocal() as db:
            user = _principal_or_none(db, user_id, organization_id)
            if user is None:
                return result, False
            session = get_owned_session(db, user, session_id) if session_id is not None else None
            return (
                _persist_turn(
                    db,
                    user=user,
                    session=session,
                    query=query,
                    result=result,
                    latency_ms=latency_ms,
                ),
                True,
            )
    except ChatPersistError:
        return result, False


def _snapshot_history(db: Session, session_id: UUID) -> list[HistoryTurn]:
    return [
        HistoryTurn(role=row.role, content=row.content)
        for row in _load_history(db, session_id)
    ]


def _load_history(db: Session, session_id: UUID) -> list[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(HISTORY_MAX_MESSAGES)
        .all()
    )
    rows.reverse()
    return rows


def _title_from_query(query: str) -> str:
    compact = " ".join(query.split())
    if len(compact) <= TITLE_MAX_LEN:
        return compact
    return compact[: TITLE_MAX_LEN - 1].rstrip() + "…"


def _persist_turn(
    db: Session,
    *,
    user: Principal,
    session: ChatSession | None,
    query: str,
    result: ChatResult,
    latency_ms: int,
) -> ChatResult:
    try:
        org = lock_organization(db, user.organization_id)
        if org is not None and result.tokens_used is not None and not has_chat_token_quota(db, org):
            result.tokens_used = None
        if session is None:
            session = ChatSession(
                organization_id=user.organization_id,
                user_id=user.id,
                title=_title_from_query(query),
            )
            db.add(session)
            db.flush()
        elif not session.title:
            session.title = _title_from_query(query)
        session.updated_at = utcnow_naive()
        now = utcnow_naive()
        db.add(
            ChatMessage(
                session_id=session.id,
                role=ChatMessageRole.user.value,
                content=query,
                sources=None,
                created_at=now,
            )
        )
        sources = [citation.model_dump(mode="json") for citation in result.citations]
        assistant = ChatMessage(
            session_id=session.id,
            role=ChatMessageRole.assistant.value,
            content=result.answer,
            sources=sources,
            created_at=now + timedelta(milliseconds=1),
        )
        db.add(assistant)
        db.flush()
        record_retrieval_audit(
            db,
            organization_id=user.organization_id,
            user_id=user.id,
            session_id=session.id,
            message_id=assistant.id,
            query=query,
            retrieved_chunk_ids=list(result.chunk_ids),
            latency_ms=latency_ms,
            tokens_used=result.tokens_used,
            commit=False,
        )
        db.commit()
        db.refresh(assistant)
        result.session_id = session.id
        result.message_id = assistant.id
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist chat turn")
        capture_pipeline_error("chat_persist", exc)
        raise ChatPersistError(PERSIST_FAILED) from exc
    return result


def _sse_from_result(result: ChatResult, *, persist_ok: bool = True) -> Iterator[str]:
    yield _sse(
        {
            "type": "citations",
            "citations": [citation.model_dump(mode="json") for citation in result.citations],
        }
    )
    if result.answer:
        yield _sse({"type": "token", "content": result.answer})
    yield from _sse_finish(result, persist_ok=persist_ok)


def _sse_finish(result: ChatResult, *, persist_ok: bool) -> Iterator[str]:
    yield _sse(_meta_payload(result))
    if not persist_ok:
        yield _sse({"type": "error", "content": PERSIST_FAILED})
    yield _sse_done()


def _meta_payload(result: ChatResult) -> dict[str, Any]:
    cost = float(result.cost_usd) if result.cost_usd is not None else None
    return {
        "type": "meta",
        "cached": result.cached,
        "tokens_used": result.tokens_used,
        "cost_usd": cost,
        "session_id": str(result.session_id) if result.session_id else None,
        "message_id": str(result.message_id) if result.message_id else None,
    }


def _sse(payload: dict | str) -> str:
    if payload == "[DONE]":
        return "data: [DONE]\n\n"
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _elapsed_ms(started: float) -> int:
    return max(int((time.perf_counter() - started) * 1000), 0)


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


__all__ = [
    "CACHE_VERSION",
    "PERSIST_FAILED",
    "SYSTEM_PROMPT",
    "ChatError",
    "ChatPersistError",
    "ChatResult",
    "HistoryTurn",
    "build_messages",
    "cache_key",
    "canonical_allowed_roles",
    "citations_from_chunks",
    "get_owned_session",
    "get_session_detail",
    "iter_sse_events",
    "list_sessions",
    "load_cached_answer",
    "question_hash",
    "retrieve",
    "save_cached_answer",
    "set_message_feedback",
]
