"""Permission-aware chat: hybrid retrieval → grounded SSE, Redis cache keyed by allowed_roles."""

from app.services.chat.prompt import (
    SYSTEM_PROMPT,
    ChatError,
    ChatPersistError,
    ChatResult,
    HistoryTurn,
    build_messages,
    citations_from_chunks,
    load_cached_answer,
    save_cached_answer,
)
from app.services.chat.sessions import (
    get_owned_session,
    get_session_detail,
    list_sessions,
    set_message_feedback,
)
from app.services.chat.sse import PERSIST_FAILED, iter_sse_events
from app.services.chat.llm_cache import CACHE_VERSION, cache_key, canonical_allowed_roles, question_hash
from app.services.retrieval import retrieve

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
