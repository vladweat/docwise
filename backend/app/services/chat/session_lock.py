"""Cross-process advisory locks for active chat-session streams."""

from collections.abc import Iterator
from contextlib import contextmanager
import hashlib
import logging
from uuid import UUID

from sqlalchemy import text

from app.core.database import engine

logger = logging.getLogger(__name__)


class ChatSessionBusyError(Exception):
    """Another stream is already active for this chat session."""


def chat_session_lock_key(session_id: UUID) -> int:
    """Return a stable signed PostgreSQL advisory-lock key for a session UUID."""
    digest = hashlib.blake2b(session_id.bytes, digest_size=8, person=b"docwise-chat").digest()
    return int.from_bytes(digest, "big", signed=True)


@contextmanager
def hold_chat_session_lock(session_id: UUID) -> Iterator[None]:
    """Fail fast if a stream owns this session; always release before pool check-in."""
    lock_key = chat_session_lock_key(session_id)
    with engine.connect() as connection:
        try:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": lock_key},
                ).scalar_one()
            )
            connection.commit()
        except Exception:
            # If acquisition succeeded but its result/commit failed, this connection may
            # still own the session lock. Discard it so PostgreSQL releases that lock.
            connection.invalidate()
            raise
        if not acquired:
            raise ChatSessionBusyError

        try:
            yield
        finally:
            try:
                released = bool(
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:lock_key)"),
                        {"lock_key": lock_key},
                    ).scalar_one()
                )
                connection.commit()
                if not released:
                    connection.invalidate()
                    logger.warning("Chat session advisory lock was not owned at release")
            except Exception as exc:
                connection.invalidate()
                logger.warning(
                    "Could not release chat session advisory lock (error_type=%s)",
                    type(exc).__name__,
                )
