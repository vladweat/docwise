from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db
from app.models.user import User
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
from app.services.llm import OpenAINotConfiguredError, OpenAIRequestError
from app.services.retrieval import RetrievalError
from app.utils.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/chat", tags=["chat"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def require_chat_limit(current_user: User = Depends(get_current_user)) -> User:
    enforce_rate_limit("chat", str(current_user.id), get_settings().rate_limit_chat_per_minute)
    return current_user


@router.post("/stream", response_model=None)
def chat_stream(
    body: ChatStreamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_chat_limit),
) -> StreamingResponse:
    if body.session_id is not None:
        get_owned_session(db, current_user, body.session_id)
    try:
        events = iter_sse_events(current_user.id, body.query, body.session_id)
        first = next(events)
    except StopIteration:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Empty chat stream",
        ) from None
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

    def _chain():
        yield first
        try:
            yield from events
        except (OpenAIRequestError, RetrievalError):
            payload = '{"type": "error", "content": "Chat failed. Try again."}'
            yield f"data: {payload}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _chain(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/sessions", response_model=ChatSessionListResponse)
def chat_sessions(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionListResponse:
    return list_sessions(db, current_user, limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetail)
def chat_session_detail(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatSessionDetail:
    return get_session_detail(db, current_user, session_id)


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
def chat_feedback(
    body: ChatFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    set_message_feedback(db, current_user, body.message_id, body.rating)
