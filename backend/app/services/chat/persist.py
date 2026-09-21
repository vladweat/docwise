"""Persist chat turns and load session history."""

from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.core.sentry import capture_pipeline_error
from app.core.time import utcnow_naive
from app.models.chat import ChatMessage, ChatMessageRole, ChatSession
from app.models.user import User
from app.services.retrieval.audit import record_retrieval_audit
from app.services.chat.prompt import (
    HISTORY_MAX_MESSAGES,
    ChatPersistError,
    ChatResult,
    HistoryTurn,
    title_from_query,
)
from app.services.chat.runtime import SessionLocal
from app.services.chat.sessions import get_owned_session
from app.services.chat.envelope import PERSIST_FAILED
from app.services.org.quotas import has_chat_token_quota, lock_organization
from app.services.org.tenancy import resolve_principal

logger = logging.getLogger(__name__)


def principal_or_none(db: Session, user_id: UUID, organization_id: UUID) -> Principal | None:
    user_row = db.get(User, user_id)
    if user_row is None or not user_row.is_active:
        return None
    return resolve_principal(db, user_row, organization_id)


def snapshot_history(db: Session, session_id: UUID) -> list[HistoryTurn]:
    return [
        HistoryTurn(role=row.role, content=row.content)
        for row in load_history(db, session_id)
    ]


def load_history(db: Session, session_id: UUID) -> list[ChatMessage]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(HISTORY_MAX_MESSAGES)
        .all()
    )
    rows.reverse()
    return rows


def persist_turn(
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


def persist_closed(
    user_id: UUID,
    organization_id: UUID,
    session_id: UUID | None,
    query: str,
    result: ChatResult,
    latency_ms: int,
) -> tuple[ChatResult, bool]:
    try:
        with SessionLocal() as db:
            user = principal_or_none(db, user_id, organization_id)
            if user is None:
                return result, False
            session = get_owned_session(db, user, session_id) if session_id is not None else None
            return (
                persist_turn(
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
