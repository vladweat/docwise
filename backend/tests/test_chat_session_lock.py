"""PostgreSQL advisory-lock behavior for serializing chat session turns."""

from __future__ import annotations

from contextlib import AbstractContextManager
from importlib import import_module
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.core.database import engine


def _lock_module():
    try:
        return import_module("app.services.chat.session_lock")
    except ModuleNotFoundError:
        pytest.fail("chat session lock service is not implemented", pytrace=False)


def _try_lock(connection, lock_key: int) -> bool:
    acquired = bool(
        connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": lock_key},
        ).scalar_one()
    )
    connection.commit()
    return acquired


def _unlock(connection, lock_key: int) -> bool:
    released = bool(
        connection.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": lock_key},
        ).scalar_one()
    )
    connection.commit()
    return released


def test_chat_session_lock_key_is_stable_signed_64_bit_value():
    lock_module = _lock_module()
    session_id = uuid4()

    first = lock_module.chat_session_lock_key(session_id)

    assert first == lock_module.chat_session_lock_key(session_id)
    assert -(2**63) <= first < 2**63


def test_chat_session_lock_rejects_nested_acquisition_for_same_session():
    lock_module = _lock_module()
    session_id = uuid4()

    with lock_module.hold_chat_session_lock(session_id):
        with pytest.raises(lock_module.ChatSessionBusyError):
            with lock_module.hold_chat_session_lock(session_id):
                pytest.fail("a second lock for the same session must not be acquired")


def test_chat_session_lock_allows_a_different_session():
    lock_module = _lock_module()

    with lock_module.hold_chat_session_lock(uuid4()):
        with lock_module.hold_chat_session_lock(uuid4()):
            pass


def test_chat_session_lock_released_after_exit_and_exception():
    lock_module = _lock_module()
    session_id = uuid4()
    lock_key = lock_module.chat_session_lock_key(session_id)

    with engine.connect() as probe:
        with lock_module.hold_chat_session_lock(session_id):
            assert _try_lock(probe, lock_key) is False
        assert _try_lock(probe, lock_key) is True
        assert _unlock(probe, lock_key) is True

        with pytest.raises(RuntimeError, match="stream interrupted"):
            with lock_module.hold_chat_session_lock(session_id):
                assert _try_lock(probe, lock_key) is False
                raise RuntimeError("stream interrupted")
        assert _try_lock(probe, lock_key) is True
        assert _unlock(probe, lock_key) is True


class _FakeResult:
    def __init__(self, value: bool) -> None:
        self.value = value

    def scalar_one(self) -> bool:
        return self.value


class _FakeConnection(AbstractContextManager):
    def __init__(
        self,
        unlock_value: bool = True,
        unlock_error: Exception | None = None,
        commit_error: Exception | None = None,
    ) -> None:
        self.unlock_value = unlock_value
        self.unlock_error = unlock_error
        self.commit_error = commit_error
        self.invalidated = False
        self.closed = False
        self.commits = 0

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.closed = True

    def execute(self, statement: Any, _params: dict[str, Any]) -> _FakeResult:
        sql = str(statement)
        if "pg_try_advisory_lock" in sql:
            return _FakeResult(True)
        if "pg_advisory_unlock" in sql:
            if self.unlock_error is not None:
                raise self.unlock_error
            return _FakeResult(self.unlock_value)
        raise AssertionError(f"unexpected advisory lock query: {sql}")

    def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    def invalidate(self) -> None:
        self.invalidated = True


class _FakeEngine:
    def __init__(self, connection: _FakeConnection) -> None:
        self.connection = connection

    def connect(self) -> _FakeConnection:
        return self.connection


@pytest.mark.parametrize(
    ("unlock_value", "unlock_error"),
    [(False, None), (True, RuntimeError("database connection lost"))],
)
def test_chat_session_lock_invalidates_connection_when_unlock_fails(
    monkeypatch: pytest.MonkeyPatch,
    unlock_value: bool,
    unlock_error: Exception | None,
):
    lock_module = _lock_module()
    connection = _FakeConnection(unlock_value=unlock_value, unlock_error=unlock_error)
    monkeypatch.setattr(lock_module, "engine", _FakeEngine(connection))

    with lock_module.hold_chat_session_lock(uuid4()):
        pass

    assert connection.invalidated
    assert connection.closed


def test_chat_session_lock_invalidates_connection_when_acquisition_commit_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    lock_module = _lock_module()
    connection = _FakeConnection(commit_error=RuntimeError("database connection lost"))
    monkeypatch.setattr(lock_module, "engine", _FakeEngine(connection))

    with pytest.raises(RuntimeError, match="database connection lost"):
        with lock_module.hold_chat_session_lock(uuid4()):
            pytest.fail("a failed acquisition commit must not enter the critical section")

    assert connection.invalidated
    assert connection.closed
