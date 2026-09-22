"""Password auth, registration, and session cookies."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth_cookies import ACCESS_COOKIE
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from helpers import register_payload, wipe_app_tables

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_tables():
    db: Session = SessionLocal()
    wipe_app_tables(db)
    db.close()
    yield
    db = SessionLocal()
    wipe_app_tables(db)
    db.close()


def _unique_email() -> str:
    return f"user-{uuid.uuid4().hex[:8]}@example.com"


def test_register_and_me():
    email = _unique_email()
    password = "securepass123"

    response = client.post(
        "/api/v1/auth/register",
        json=register_payload(email, password, organization_name="Acme"),
    )
    assert response.status_code == 201
    body = response.json()
    assert "access_token" not in body
    uuid.UUID(body["id"])
    uuid.UUID(body["organization_id"])
    assert body["email"] == email
    assert body["role"] == "admin"
    assert body["organization_name"] == "Acme"

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    data = me.json()
    assert data["email"] == email
    assert data["role"] == "admin"
    assert data["departments"] == []
    assert data["is_active"] is True
    assert data["organization_name"] == "Acme"
    assert "hashed_password" not in data
    uuid.UUID(data["id"])
    uuid.UUID(data["organization_id"])


def test_register_requires_organization_name():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "securepass123"},
    )
    assert response.status_code == 422


def test_second_register_creates_separate_org():
    first = _unique_email()
    second = _unique_email()
    a = client.post("/api/v1/auth/register", json=register_payload(first, organization_name="Acme"))
    assert a.status_code == 201
    client.cookies.clear()
    b = client.post("/api/v1/auth/register", json=register_payload(second, organization_name="Globex"))
    assert b.status_code == 201
    assert b.json()["role"] == "admin"
    assert b.json()["organization_id"] != a.json()["organization_id"]
    assert b.json()["organization_name"] == "Globex"


def test_register_duplicate_email():
    email = _unique_email()
    payload = register_payload(email)

    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_login_success():
    email = _unique_email()
    password = "securepass123"
    client.post("/api/v1/auth/register", json=register_payload(email, password, organization_name="Acme"))
    client.cookies.clear()

    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    assert body["email"] == email
    assert body["organization_name"] == "Acme"
    assert client.get("/api/v1/auth/me").status_code == 200


def test_login_wrong_password():
    email = _unique_email()
    client.post("/api/v1/auth/register", json=register_payload(email))

    response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrongpassword"})
    assert response.status_code == 401


def test_me_unauthorized():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_bearer_header_is_ignored():
    email = _unique_email()
    registered = client.post("/api/v1/auth/register", json=register_payload(email))
    org_id = registered.json()["organization_id"]
    token = create_access_token(email, org_id=org_id)
    client.cookies.clear()
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 401


def test_google_not_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()

    response = client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 503

    get_settings.cache_clear()


def test_google_auth_success(monkeypatch):
    email = _unique_email()
    google_sub = f"google-{uuid.uuid4().hex[:8]}"

    def fake_verify(token: str, client_id: str) -> dict:
        assert token == "valid-token"
        assert client_id == "test-client-id.apps.googleusercontent.com"
        return {"sub": google_sub, "email": email, "email_verified": True}

    from app.core.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.v1.auth.verify_google_id_token", fake_verify)

    missing = client.post("/api/v1/auth/google", json={"id_token": "valid-token"})
    assert missing.status_code == 400

    response = client.post(
        "/api/v1/auth/google",
        json={"id_token": "valid-token", "organization_name": "Globex"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    uuid.UUID(body["id"])
    assert body["email"] == email
    assert body["role"] == "admin"
    assert body["organization_name"] == "Globex"
    assert client.get("/api/v1/auth/me").status_code == 200

    get_settings.cache_clear()


def test_google_rejects_unverified_email(monkeypatch):
    def fake_verify(token: str, client_id: str) -> dict:
        return {"sub": "google-unverified", "email": "nope@example.com", "email_verified": False}

    from app.core.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.v1.auth.verify_google_id_token", fake_verify)

    response = client.post(
        "/api/v1/auth/google",
        json={"id_token": "valid-token", "organization_name": "Acme"},
    )
    assert response.status_code == 401
    get_settings.cache_clear()


def test_admin_role_via_cookie():
    email = _unique_email()
    registered = client.post("/api/v1/auth/register", json=register_payload(email, organization_name="Acme"))
    org_id = registered.json()["organization_id"]
    token = create_access_token(email, org_id=org_id)
    client.cookies.clear()
    client.cookies.set(ACCESS_COOKIE, token)
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "admin"
    assert body["departments"] == []
    assert body["organization_name"] == "Acme"
    uuid.UUID(body["id"])
