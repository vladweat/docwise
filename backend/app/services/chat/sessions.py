"""Chat session CRUD and feedback. Streaming lives in `chat.py`."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.principal import Principal
from app.models.audit import RagAuditLog
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.schemas.chat import ChatMessageOut, ChatSessionDetail, ChatSessionListResponse, ChatSessionSummary, Citation

NOT_FOUND_DETAIL = "Chat session not found"
MESSAGE_NOT_FOUND_DETAIL = "Chat message not found"


def get_owned_session(db: Session, user: Principal, session_id: UUID) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
            ChatSession.organization_id == user.organization_id,
        )
        .first()
    )
    if session is None:
        raise NotFoundError(NOT_FOUND_DETAIL)
    return session


def list_sessions(
    db: Session,
    user: Principal,
    *,
    limit: int = 20,
    offset: int = 0,
) -> ChatSessionListResponse:
    query = db.query(ChatSession).filter(
        ChatSession.user_id == user.id,
        ChatSession.organization_id == user.organization_id,
    )
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


def message_out(row: ChatMessage) -> ChatMessageOut:
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


def get_session_detail(db: Session, user: Principal, session_id: UUID) -> ChatSessionDetail:
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
        messages=[message_out(row) for row in messages],
    )


def set_message_feedback(db: Session, user: Principal, message_id: UUID, rating: int) -> None:
    message = (
        db.query(ChatMessage)
        .join(ChatSession, ChatSession.id == ChatMessage.session_id)
        .filter(
            ChatMessage.id == message_id,
            ChatSession.user_id == user.id,
            ChatSession.organization_id == user.organization_id,
        )
        .first()
    )
    if message is None:
        raise NotFoundError(MESSAGE_NOT_FOUND_DETAIL)
    if message.role != ChatMessageRole.assistant.value:
        raise NotFoundError(MESSAGE_NOT_FOUND_DETAIL)

    log = (
        db.query(RagAuditLog)
        .filter(RagAuditLog.message_id == message.id, RagAuditLog.user_id == user.id)
        .order_by(RagAuditLog.created_at.desc())
        .first()
    )
    if log is None:
        log = RagAuditLog(
            organization_id=user.organization_id,
            user_id=user.id,
            session_id=message.session_id,
            message_id=message.id,
            query="",
            retrieved_chunk_ids=[],
        )
        db.add(log)
    log.feedback = rating
    db.commit()


def delete_session(db: Session, user: Principal, session_id: UUID) -> None:
    session = get_owned_session(db, user, session_id)
    db.delete(session)
    db.commit()
