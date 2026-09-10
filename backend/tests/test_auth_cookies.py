import uuid

from fastapi.testclient import TestClient

from app.core.auth_cookies import ACCESS_COOKIE, REFRESH_COOKIE
from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from helpers import register_payload

client = TestClient(app)


def _unique_email() -> str:
    return f"cookie-{uuid.uuid4().hex[:8]}@example.com"


def test_register_sets_httponly_cookies():
    email = _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
    )
    assert response.status_code == 201
    assert ACCESS_COOKIE in response.cookies
    assert REFRESH_COOKIE in response.cookies
    header = response.headers.get("set-cookie") or ""
    assert "httponly" in header.lower()
    assert ACCESS_COOKIE == "dw_access"
    assert REFRESH_COOKIE == "dw_refresh"
    assert "access_token" not in response.json()

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_logout_clears_cookies():
    email = _unique_email()
    client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
    )
    assert client.get("/api/v1/auth/me").status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotates_cookies():
    email = _unique_email()
    client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
    )
    first_refresh = client.cookies.get(REFRESH_COOKIE)
    rotated = client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["email"] == email
    assert "access_token" not in rotated.json()
    assert client.cookies.get(REFRESH_COOKIE) != first_refresh
    assert client.get("/api/v1/auth/me").status_code == 200


def test_refresh_token_cannot_be_used_as_bearer():
    email = _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
    )
    refresh = response.cookies.get(REFRESH_COOKIE)
    client.cookies.clear()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert me.status_code == 401


def test_access_cookie_without_typ_claim():
    email = _unique_email()
    registered = client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
    )
    assert registered.status_code == 201
    token = create_access_token(
        email,
        role=registered.json()["role"],
        org_id=registered.json()["organization_id"],
    )
    client.cookies.clear()
    client.cookies.set(ACCESS_COOKIE, token)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200


def test_csrf_required_when_samesite_none(monkeypatch):
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    get_settings.cache_clear()
    email = _unique_email()
    try:
        blocked = client.post(
            "/api/v1/auth/register",
            json=register_payload(email),
        )
        assert blocked.status_code == 403
        allowed = client.post(
            "/api/v1/auth/register",
            json=register_payload(email),
            headers={"X-Requested-With": "Docwise"},
        )
        assert allowed.status_code == 201
    finally:
        get_settings.cache_clear()
