"""Redis fixed-window rate limits."""

import uuid

import pytest
from fastapi import HTTPException

from app.core.rate_limit import enforce_rate_limit


def test_enforce_rate_limit_blocks_after_limit():
    user_id = str(uuid.uuid4())
    enforce_rate_limit("upload", user_id, 1)
    with pytest.raises(HTTPException) as exc:
        enforce_rate_limit("upload", user_id, 1)
    assert exc.value.status_code == 429
    assert exc.value.headers and exc.value.headers.get("Retry-After")


def test_enforce_rate_limit_disabled():
    user_id = str(uuid.uuid4())
    enforce_rate_limit("upload", user_id, 0)
    enforce_rate_limit("upload", user_id, 0)


def test_auth_login_rate_limit(monkeypatch):
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.core.database import SessionLocal
    from app.main import app
    from helpers import register_payload, wipe_app_tables

    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "1")
    monkeypatch.setenv("RATE_LIMIT_TRUST_X_FORWARDED_FOR", "true")
    get_settings.cache_clear()
    client = TestClient(app)
    email = f"rl-{uuid.uuid4().hex[:8]}@example.com"
    ip = f"203.0.113.{uuid.uuid4().int % 200 + 1}"
    headers = {"X-Forwarded-For": ip}
    db = SessionLocal()
    wipe_app_tables(db)
    db.close()
    first = client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "securepass123"},
        headers=headers,
    )
    assert second.status_code == 429
