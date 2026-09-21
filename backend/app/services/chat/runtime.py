"""Chat stream dependencies (patchable in tests via ``app.services.chat`` re-exports)."""

from app.core.database import SessionLocal
from app.services.chat.llm import stream_openai
from app.services.retrieval import embed_query, finish_retrieval, hybrid_search

__all__ = [
    "SessionLocal",
    "embed_query",
    "finish_retrieval",
    "hybrid_search",
    "stream_openai",
]
