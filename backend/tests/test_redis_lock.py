"""Per-document indexing lock in Redis."""

from contextvars import Context
from uuid import uuid4

from app.core.redis import acquire_indexing_lock, is_indexing_locked, lock_key, release_indexing_lock


def test_indexing_lock_roundtrip():
    document_id = str(uuid4())
    release_indexing_lock(document_id)
    assert lock_key(document_id) == f"indexing_lock:{document_id}"
    assert acquire_indexing_lock(document_id) is True
    assert is_indexing_locked(document_id) is True
    assert Context().run(acquire_indexing_lock, document_id) is False
    release_indexing_lock(document_id)
    assert is_indexing_locked(document_id) is False
