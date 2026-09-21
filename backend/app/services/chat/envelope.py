"""SSE JSON line helpers for chat streaming."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from app.services.chat.prompt import ChatResult

PERSIST_FAILED = "Chat was not saved. Try again."


def sse(payload: dict | str) -> str:
    if payload == "[DONE]":
        return "data: [DONE]\n\n"
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"


def meta_payload(result: ChatResult) -> dict[str, Any]:
    cost = float(result.cost_usd) if result.cost_usd is not None else None
    return {
        "type": "meta",
        "cached": result.cached,
        "tokens_used": result.tokens_used,
        "cost_usd": cost,
        "session_id": str(result.session_id) if result.session_id else None,
        "message_id": str(result.message_id) if result.message_id else None,
    }


def sse_from_result(result: ChatResult, *, persist_ok: bool = True) -> Iterator[str]:
    yield sse(
        {
            "type": "citations",
            "citations": [citation.model_dump(mode="json") for citation in result.citations],
        }
    )
    if result.answer:
        yield sse({"type": "token", "content": result.answer})
    yield from sse_finish(result, persist_ok=persist_ok)


def sse_finish(result: ChatResult, *, persist_ok: bool) -> Iterator[str]:
    yield sse(meta_payload(result))
    if not persist_ok:
        yield sse({"type": "error", "content": PERSIST_FAILED})
    yield sse_done()
