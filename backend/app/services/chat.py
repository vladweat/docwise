"""Permission-aware chat: hybrid retrieval → grounded SSE, Redis cache keyed by allowed_roles."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.sentry import capture_pipeline_error
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession, RagAuditLog
from app.models.user import User
from app.schemas.chat import (
    ChatMessageOut,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatSessionSummary,
    Citation,
)
from app.services.llm import (
    LLMUsage,
    OpenAINotConfiguredError,
    OpenAIRequestError,
    openai_is_configured,
    stream_openai,
)
from app.services.retrieval import NO_CONTEXT_ANSWER, RetrievedChunk, allowed_roles_for, retrieve
from app.utils.redis_lock import get_redis_client

logger = logging.getLogger(__name__)

CACHE_VERSION = "v1"
LLM_CACHE_TTL_SECONDS = 86400
HISTORY_MAX_MESSAGES = 8
TITLE_MAX_LEN = 80
GENERIC_CHAT_ERROR = "Chat failed. Try again."
NOT_FOUND_DETAIL = "Chat session not found"
MESSAGE_NOT_FOUND_DETAIL = "Chat message not found"

SYSTEM_PROMPT = (
    "You are a corporate AI assistant. Answer strictly using the provided document excerpts. "
    "If the excerpts do not contain the answer, reply exactly: "
    f"«{NO_CONTEXT_ANSWER}» "
    "Do not invent facts, numbers, or policies. "
    "Every factual statement must cite the document title and page "
    "in the form [Title.pdf, p. N]. Reply in the same language as the user's question."
)


class ChatError(Exception):
    """Raised when chat orchestration fails."""


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


def canonical_allowed_roles(roles: Sequence[str]) -> tuple[str, ...]:
    """Stable, sorted unique roles for cache keys and ACL. Never from the request body."""
    return tuple(sorted({str(role).strip() for role in roles if str(role).strip()}))


def question_hash(question: str) -> str:
    return hashlib.sha256(f"{CACHE_VERSION}\n{question.strip()}".encode("utf-8")).hexdigest()


def cache_key(question: str, allowed_roles: Sequence[str]) -> str:
    roles = canonical_allowed_roles(allowed_roles)
    roles_hash = hashlib.sha256(",".join(roles).encode("utf-8")).hexdigest()[:16]
    return f"llm_cache:{CACHE_VERSION}:{roles_hash}:{question_hash(question)}"


def citations_from_chunks(chunks: Sequence[RetrievedChunk]) -> list[Citation]:
    return [Citation.model_validate(chunk.to_citation()) for chunk in chunks]


def build_messages(
    question: str,
    chunks: Sequence[RetrievedChunk],
    history: Sequence[ChatMessage] = (),
) -> list[dict[str, str]]:
    """LLM messages. Context is only the current ACL-filtered Top-4; history is dialogue, not retrieval."""
    parts: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        title = chunk.doc_title or "Document"
        parts.append(f"[{index}] {title} | page {chunk.page_number}\n{chunk.content}")
    context = "\n\n".join(parts) if parts else "(no excerpts)"
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Document excerpts:\n{context}"},
    ]
    for row in history:
        if row.role not in {ChatMessageRole.user.value, ChatMessageRole.assistant.value}:
            continue
        messages.append({"role": row.role, "content": row.content})
    messages.append({"role": "user", "content": question})
    return messages


def get_owned_session(db: Session, user: User, session_id: UUID) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND_DETAIL)
    return session


def list_sessions(
    db: Session,
    user: User,
    *,
    limit: int = 20,
    offset: int = 0,
) -> ChatSessionListResponse:
    query = db.query(ChatSession).filter(ChatSession.user_id == user.id)
    total = query.count()
    rows = (
        query.order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ChatSessionListResponse(
        items=[ChatSessionSummary.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_session_detail(db: Session, user: User, session_id: UUID) -> ChatSessionDetail:
    session = get_owned_session(db, user, session_id)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .all()
    )
    return ChatSessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_message_out(row) for row in messages],
    )


def set_message_feedback(db: Session, user: User, message_id: UUID, rating: int) -> None:
    message = (
        db.query(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(ChatMessage.id == message_id, ChatSession.user_id == user.id)
        .first()
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MESSAGE_NOT_FOUND_DETAIL)
    if message.role != ChatMessageRole.assistant.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=MESSAGE_NOT_FOUND_DETAIL)

    log = (
        db.query(RagAuditLog)
        .filter(RagAuditLog.message_id == message.id, RagAuditLog.user_id == user.id)
        .order_by(RagAuditLog.created_at.desc())
        .first()
    )
    if log is None:
        log = RagAuditLog(
            user_id=user.id,
            session_id=message.session_id,
            message_id=message.id,
            query="",
            retrieved_chunk_ids=[],
        )
        db.add(log)
    log.feedback = rating
    db.commit()


def iter_sse_events(
    user_id: UUID,
    query: str,
    session_id: UUID | None,
    *,
    retriever=None,
    streamer=None,
) -> Iterator[str]:
    started = time.perf_counter()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if user is None or not user.is_active:
            yield _sse({"type": "error", "content": GENERIC_CHAT_ERROR})
            yield _sse_done()
            return

        session = get_owned_session(db, user, session_id) if session_id is not None else None
        allowed = canonical_allowed_roles(allowed_roles_for(user))
        history = _load_history(db, session.id) if session is not None else []

        cached = load_cached_answer(query, allowed)
        if cached is not None:
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
            yield from _sse_from_result(cached)
            return

        search = retriever or retrieve
        retrieval = search(db, user, query)
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
            persist = _persist_turn(
                db,
                user=user,
                session=session,
                query=query,
                result=result,
                latency_ms=_elapsed_ms(started),
            )
            result.session_id = persist.session_id
            result.message_id = persist.message_id
            save_cached_answer(query, allowed, result)
            yield _sse({"type": "token", "content": result.answer})
            yield _sse(_meta_payload(result))
            yield _sse_done()
            return

        messages = build_messages(query, chunks, history)
        generate = streamer or stream_openai
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
        persist = _persist_turn(
            db,
            user=user,
            session=session,
            query=query,
            result=result,
            latency_ms=_elapsed_ms(started),
        )
        result.session_id = persist.session_id
        result.message_id = persist.message_id
        save_cached_answer(query, allowed, result)
        yield _sse(_meta_payload(result))
        yield _sse_done()
    except (OpenAINotConfiguredError, OpenAIRequestError, ChatError):
        raise
    except HTTPException:
        raise
    except Exception as exc:
        capture_pipeline_error("chat", exc)
        logger.exception("Chat stream failed")
        yield _sse({"type": "error", "content": GENERIC_CHAT_ERROR})
        yield _sse_done()
    finally:
        db.close()


def load_cached_answer(question: str, allowed_roles: Sequence[str]) -> ChatResult | None:
    payload = _redis_get(cache_key(question, allowed_roles))
    if payload is None:
        return None
    return _result_from_cache_payload(payload)


def save_cached_answer(question: str, allowed_roles: Sequence[str], result: ChatResult) -> None:
    _redis_set(cache_key(question, allowed_roles), _cache_payload(result))


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
    user: User,
    session: ChatSession | None,
    query: str,
    result: ChatResult,
    latency_ms: int,
) -> ChatResult:
    try:
        if session is None:
            session = ChatSession(user_id=user.id, title=_title_from_query(query))
            db.add(session)
            db.flush()
        elif not session.title:
            session.title = _title_from_query(query)
        session.updated_at = datetime.now()
        now = datetime.now()
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
        db.add(
            RagAuditLog(
                user_id=user.id,
                session_id=session.id,
                message_id=assistant.id,
                query=query,
                retrieved_chunk_ids=list(result.chunk_ids),
                latency_ms=latency_ms,
                tokens_used=result.tokens_used,
            )
        )
        db.commit()
        db.refresh(assistant)
        result.session_id = session.id
        result.message_id = assistant.id
    except Exception:
        db.rollback()
        logger.exception("Failed to persist chat turn")
    return result


def _message_out(row: ChatMessage) -> ChatMessageOut:
    citations: list[Citation] = []
    for item in row.sources or []:
        if not isinstance(item, dict):
            continue
        try:
            citations.append(Citation.model_validate(item))
        except Exception:
            continue
    return ChatMessageOut(
        id=row.id,
        role=row.role,
        content=row.content,
        sources=citations,
        created_at=row.created_at,
    )


def _sse_from_result(result: ChatResult) -> Iterator[str]:
    yield _sse(
        {
            "type": "citations",
            "citations": [citation.model_dump(mode="json") for citation in result.citations],
        }
    )
    if result.answer:
        yield _sse({"type": "token", "content": result.answer})
    yield _sse(_meta_payload(result))
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
        "tokens_used": result.tokens_used,
        "cost_usd": str(result.cost_usd) if result.cost_usd is not None else None,
        "chunk_ids": list(result.chunk_ids),
    }


def _result_from_cache_payload(payload: dict[str, Any]) -> ChatResult:
    cost_raw = payload.get("cost_usd")
    cost = Decimal(str(cost_raw)) if cost_raw is not None else None
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
        tokens_used=payload.get("tokens_used"),
        cost_usd=cost,
        chunk_ids=chunk_ids,
    )


def _redis_get(key: str) -> dict | None:
    try:
        value = get_redis_client().get(key)
    except Exception as exc:
        logger.warning("Redis cache get failed: %s", exc)
        return None
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _redis_set(key: str, payload: dict) -> None:
    try:
        get_redis_client().set(key, json.dumps(payload, ensure_ascii=False), ex=LLM_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Redis cache set failed: %s", exc)
