"""SSE streaming orchestration for chat (retrieval → tokens → persist)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.errors import NotFoundError
from app.core.principal import Principal
from app.core.sentry import capture_pipeline_error
from app.core.time import utcnow_naive
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.user import User
from app.services.retrieval.audit import record_retrieval_audit
from app.services.chat.prompt import (
    HISTORY_MAX_MESSAGES,
    ChatError,
    ChatPersistError,
    ChatResult,
    HistoryTurn,
    build_messages,
    citations_from_chunks,
    load_cached_answer,
    save_cached_answer,
    title_from_query,
)
from app.services.chat.sessions import get_owned_session
from app.services.chat.llm import (
    LLMUsage,
    OpenAINotConfiguredError,
    OpenAIRequestError,
    openai_is_configured,
    stream_openai,
)
from app.services.chat.llm_cache import canonical_allowed_roles
from app.services.org.quotas import QUOTA_EXCEEDED, has_chat_token_quota, lock_organization
from app.services.retrieval import (
    NO_CONTEXT_ANSWER,
    allowed_roles_for,
    embed_query,
    finish_retrieval,
    hybrid_search,
    retrieve as retrieval_retrieve,
)
from app.services.org.tenancy import resolve_principal

logger = logging.getLogger(__name__)

GENERIC_CHAT_ERROR = "Chat failed. Try again."
PERSIST_FAILED = "Chat was not saved. Try again."


def _active_retrieve():
    """Late-bind so tests can monkeypatch ``app.services.chat.retrieve``."""
    from app.services.chat import retrieve

    return retrieve


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
    search = retriever if retriever is not None else _active_retrieve()
    generate = streamer or stream_openai
    use_split = retriever is None and search is retrieval_retrieve

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
                title=title_from_query(query),
            )
            db.add(session)
            db.flush()
        elif not session.title:
            session.title = title_from_query(query)
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
