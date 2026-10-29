"""Chat SSE stream and sessions; retrieval uses session org + ACL."""

from collections.abc import Callable, Generator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.types import Receive, Scope, Send

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.core.errors import ConflictError
from app.core.principal import Principal
from app.core.rate_limit import enforce_rate_limit
from app.schemas.chat import (
    ChatFeedbackRequest,
    ChatSessionDetail,
    ChatSessionListResponse,
    ChatStreamRequest,
)
from app.services.chat import (
    get_owned_session,
    get_session_detail,
    iter_sse_events,
    list_sessions,
    set_message_feedback,
)
from app.services.chat.sessions import delete_session
from app.services.chat.session_lock import ChatSessionBusyError
from app.services.chat.llm import OpenAINotConfiguredError, OpenAIRequestError
from app.services.retrieval import RetrievalError

router = APIRouter(prefix="/chat", tags=["chat"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
_SESSION_BUSY_DETAIL = "A reply is already being generated for this chat. Try again shortly."


class ClosingStreamingResponse(StreamingResponse):
    """Close the lock-owning generator on every ASGI response exit, including disconnect."""

    def __init__(
        self,
        content: Generator[str, None, None],
        *,
        close_callback: Callable[[], None],
        **kwargs,
    ) -> None:
        self._content = content
        self._close_callback = close_callback
        super().__init__(content, **kwargs)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            try:
                self._content.close()
            finally:
                self._close_callback()


def require_chat_limit(current_user: Principal = Depends(get_current_user)) -> Principal:
    enforce_rate_limit("chat", str(current_user.id), get_settings().rate_limit_chat_per_minute)
    return current_user


def chain_chat_events(first: str, events: Generator[str, None, None]) -> Generator[str, None, None]:
    """Chain the first SSE event and close the underlying iterator on cancellation."""
    try:
        yield first
        try:
            yield from events
        except (OpenAIRequestError, RetrievalError):
            payload = '{"type": "error", "content": "Chat failed. Try again."}'
            yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"
    finally:
        events.close()


@router.post("/stream", response_model=None)
def chat_stream(
    body: ChatStreamRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_chat_limit),
) -> StreamingResponse:
    if body.session_id is not None:
        get_owned_session(db, current_user, body.session_id)
    try:
        events = iter_sse_events(
            current_user.id,
            body.query,
            body.session_id,
            organization_id=current_user.organization_id,
        )
        first = next(events)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Empty chat stream",
        ) from None
    except ChatSessionBusyError as exc:
        raise ConflictError(_SESSION_BUSY_DETAIL) from exc
    except OpenAINotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (OpenAIRequestError, RetrievalError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat failed. Try again.",
        ) from exc

    return ClosingStreamingResponse(
        chain_chat_events(first, events),
        close_callback=events.close,
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
def chat_sessions(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(get_current_user),
) -> ChatSessionListResponse:
    return list_sessions(db, current_user, limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def chat_session_detail(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(get_current_user),
) -> ChatSessionDetail:
    return get_session_detail(db, current_user, session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def chat_session_delete(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(get_current_user),
) -> None:
    delete_session(db, current_user, session_id)


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
def chat_feedback(
    body: ChatFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(get_current_user),
) -> None:
    set_message_feedback(db, current_user, body.message_id, body.rating, body.comment)
