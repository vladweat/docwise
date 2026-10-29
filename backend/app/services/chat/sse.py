"""SSE streaming orchestration for chat (retrieval → tokens → persist)."""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from uuid import UUID

from app.core.errors import NotFoundError
from app.core.rls import bind_session_rls
from app.core.sentry import capture_pipeline_error
from app.models.chat import ChatSession
from app.services.chat.session_lock import hold_chat_session_lock
from app.services.chat.envelope import PERSIST_FAILED, sse, sse_done, sse_finish, sse_from_result
from app.services.chat.llm import (
    LLMUsage,
    OpenAINotConfiguredError,
    OpenAIRequestError,
    openai_is_configured,
)
from app.services.chat.llm_cache import canonical_allowed_roles
from app.services.chat.persist import persist_closed, persist_turn, principal_or_none, snapshot_history
from app.services.chat.prompt import (
    ChatError,
    ChatPersistError,
    ChatResult,
    build_messages,
    citations_from_chunks,
    load_cached_answer,
    save_cached_answer,
    title_from_query,
)
from app.services.chat.sessions import get_owned_session
from app.services.org.quotas import QUOTA_EXCEEDED, has_chat_token_quota
from app.services.retrieval import NO_CONTEXT_ANSWER, allowed_roles_for, retrieve as retrieval_retrieve

logger = logging.getLogger(__name__)

GENERIC_CHAT_ERROR = "Chat failed. Try again."

# Tests monkeypatch ``app.services.chat._persist_turn``.
_persist_turn = persist_turn


def _chat():
    """Late-bind package attrs so tests can monkeypatch ``app.services.chat.*``."""
    import app.services.chat as chat

    return chat


def iter_sse_events(
    user_id: UUID,
    query: str,
    session_id: UUID | None,
    *,
    organization_id: UUID,
    retriever=None,
    streamer=None,
) -> Generator[str, None, None]:
    if session_id is None:
        yield from _iter_sse_events_impl(
            user_id,
            query,
            session_id,
            organization_id=organization_id,
            retriever=retriever,
            streamer=streamer,
        )
        return

    with hold_chat_session_lock(session_id):
        yield from _iter_sse_events_impl(
            user_id,
            query,
            session_id,
            organization_id=organization_id,
            retriever=retriever,
            streamer=streamer,
        )


def _iter_sse_events_impl(
    user_id: UUID,
    query: str,
    session_id: UUID | None,
    *,
    organization_id: UUID,
    retriever=None,
    streamer=None,
) -> Generator[str, None, None]:
    started = time.perf_counter()
    chat = _chat()
    search = retriever if retriever is not None else chat.retrieve
    generate = streamer or chat.stream_openai
    session_local = chat.SessionLocal
    use_split = retriever is None and search is retrieval_retrieve

    try:
        with session_local() as db:
            bind_session_rls(db, organization_id=organization_id)
            user = principal_or_none(db, user_id, organization_id)
            if user is None:
                yield sse({"type": "error", "content": GENERIC_CHAT_ERROR})
                yield sse_done()
                return
            if not has_chat_token_quota(db, user.organization):
                yield sse({"type": "error", "content": QUOTA_EXCEEDED})
                yield sse_done()
                return

            session = get_owned_session(db, user, session_id) if session_id is not None else None
            allowed = canonical_allowed_roles(allowed_roles_for(user))
            history = snapshot_history(db, session.id) if session is not None else []
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
                    persist = chat._persist_turn(
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
                yield from sse_from_result(cached, persist_ok=persist_ok)
                return

        retrieval = _run_retrieval(
            search,
            user_id,
            organization_id,
            query,
            use_split=use_split,
        )
        if retrieval is None:
            yield sse({"type": "error", "content": GENERIC_CHAT_ERROR})
            yield sse_done()
            return

        chunks = list(retrieval.chunks)
        citations = citations_from_chunks(chunks)
        if chunks and not openai_is_configured() and streamer is None:
            raise OpenAINotConfiguredError("OPENAI_API_KEY is not configured")

        if session_id is None:
            session_id = _create_chat_session(
                session_local,
                user_id,
                organization_id,
                query,
            )
            if session_id is None:
                yield sse({"type": "error", "content": GENERIC_CHAT_ERROR})
                yield sse_done()
                return
            yield sse(
                {
                    "type": "meta",
                    "cached": False,
                    "tokens_used": None,
                    "cost_usd": None,
                    "session_id": str(session_id),
                    "message_id": None,
                }
            )

        yield sse(
            {
                "type": "citations",
                "citations": [citation.model_dump(mode="json") for citation in citations],
            }
        )

        if not chunks:
            result = ChatResult(answer=NO_CONTEXT_ANSWER, citations=[], cached=False, chunk_ids=[])
            result, persist_ok = persist_closed(
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
            yield sse({"type": "token", "content": result.answer})
            yield from sse_finish(result, persist_ok=persist_ok)
            return

        messages = build_messages(query, chunks, history)
        parts: list[str] = []
        usage = LLMUsage()
        for item in generate(messages):
            if isinstance(item, LLMUsage):
                usage = item
                continue
            parts.append(item)
            yield sse({"type": "token", "content": item})

        result = ChatResult(
            answer="".join(parts),
            citations=citations,
            cached=False,
            tokens_used=usage.tokens_used,
            cost_usd=usage.cost_usd,
            chunk_ids=[str(chunk.id) for chunk in chunks],
        )
        result, persist_ok = persist_closed(
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
        yield from sse_finish(result, persist_ok=persist_ok)
    except ChatPersistError:
        yield sse({"type": "error", "content": PERSIST_FAILED})
        yield sse_done()
    except (OpenAINotConfiguredError, OpenAIRequestError, ChatError):
        raise
    except NotFoundError:
        raise
    except Exception as exc:
        capture_pipeline_error("chat", exc)
        logger.exception("Chat stream failed")
        yield sse({"type": "error", "content": GENERIC_CHAT_ERROR})
        yield sse_done()


def _run_retrieval(search, user_id: UUID, organization_id: UUID, query: str, *, use_split: bool):
    chat = _chat()
    session_local = chat.SessionLocal
    if use_split:
        vector = chat.embed_query(query)
        with session_local() as db:
            bind_session_rls(db, organization_id=organization_id)
            user = principal_or_none(db, user_id, organization_id)
            if user is None:
                return None
            pool = chat.hybrid_search(db, user, query, vector)
        return chat.finish_retrieval(query, pool)

    with session_local() as db:
        bind_session_rls(db, organization_id=organization_id)
        user = principal_or_none(db, user_id, organization_id)
        if user is None:
            return None
        return search(db, user, query)


def _create_chat_session(session_local, user_id: UUID, organization_id: UUID, query: str) -> UUID | None:
    with session_local() as db:
        bind_session_rls(db, organization_id=organization_id)
        user = principal_or_none(db, user_id, organization_id)
        if user is None:
            return None
        session = ChatSession(
            organization_id=user.organization_id,
            user_id=user.id,
            title=title_from_query(query),
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id


def _elapsed_ms(started: float) -> int:
    return max(int((time.perf_counter() - started) * 1000), 0)
