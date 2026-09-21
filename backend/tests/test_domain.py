"""M6d: platform/custom host pins org; host-only cookies; unverified host does not bind."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth_cookies import ACCESS_COOKIE
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document, DocumentStatus
from app.models.organization import Organization
from app.services.org.domains import (
    DOMAIN_NOT_IN_PLAN,
    HOST_SWITCH_DENIED,
    HOSTNAME_IN_USE,
    hostname_is_bound,
    origin_allowed,
    resolve_bound_organization,
)
from helpers import register_payload, set_org_plan, wipe_app_tables


@pytest.fixture(autouse=True)
def clean_tables():
    db: Session = SessionLocal()
    wipe_app_tables(db)
    db.close()
    yield
    db = SessionLocal()
    wipe_app_tables(db)
    db.close()


def _register(name: str, password: str = "securepass123") -> tuple[TestClient, str]:
    http = TestClient(app)
    email = f"{name.lower()}-{uuid4().hex[:8]}@example.com"
    response = http.post(
        "/api/v1/auth/register",
        json=register_payload(email, password, organization_name=name),
    )
    assert response.status_code == 201
    return http, email


def _org_id(http: TestClient) -> UUID:
    return UUID(http.get("/api/v1/auth/me").json()["organization_id"])


def _slug_for(http: TestClient) -> str:
    org_id = _org_id(http)
    db = SessionLocal()
    org = db.get(Organization, org_id)
    assert org is not None
    slug = org.slug
    db.close()
    return slug


def _enterprise(http: TestClient) -> None:
    db = SessionLocal()
    set_org_plan(db, _org_id(http), "enterprise")
    db.close()


def _host(slug: str) -> dict[str, str]:
    return {"Host": f"{slug}.localhost"}


def test_starter_cannot_put_custom_hostname():
    http, _email = _register("Acme")
    response = http.put("/api/v1/organizations/domain", json={"hostname": "kb.acme.example"})
    assert response.status_code == 403
    assert response.json()["detail"] == DOMAIN_NOT_IN_PLAN
    listed = http.get("/api/v1/organizations/domain")
    assert listed.status_code == 200
    body = listed.json()
    assert body["entitlement"] is False
    assert body["custom_hostname"] is None
    slug = body["slug"]
    assert f"{slug}.localhost" in body["platform_hostnames"]
    assert f"{slug}.docwise.app" in body["platform_hostnames"]


def test_put_own_platform_hostname_is_noop():
    http, _email = _register("Bootorg")
    _enterprise(http)
    listed = http.get("/api/v1/organizations/domain")
    assert listed.status_code == 200
    slug = listed.json()["slug"]
    platform = f"{slug}.docwise.app"
    response = http.put("/api/v1/organizations/domain", json={"hostname": platform})
    assert response.status_code == 200
    body = response.json()
    assert body["custom_hostname"] is None
    assert body["custom_verified"] is False
    assert platform in body["platform_hostnames"]
    localhost = http.put("/api/v1/organizations/domain", json={"hostname": f"{slug}.localhost"})
    assert localhost.status_code == 200
    assert localhost.json()["custom_hostname"] is None


def test_put_unused_platform_style_hostname_as_custom():
    http, _email = _register("Bootorg")
    _enterprise(http)
    response = http.put("/api/v1/organizations/domain", json={"hostname": "bootorg.docwise.app"})
    assert response.status_code == 200
    body = response.json()
    assert body["custom_hostname"] == "bootorg.docwise.app"
    assert body["custom_verified"] is False
    assert body["verification_token"]


def test_put_other_org_platform_hostname_does_not_bind():
    acme, _a = _register("Acme")
    globex, _g = _register("Globex")
    _enterprise(globex)
    acme_slug = _slug_for(acme)
    taken = globex.put("/api/v1/organizations/domain", json={"hostname": f"{acme_slug}.docwise.app"})
    assert taken.status_code == 409
    assert taken.json()["detail"] == HOSTNAME_IN_USE
    assert "acme" not in taken.text.lower()
    assert globex.get("/api/v1/organizations/domain").json()["custom_hostname"] is None


def test_employee_cannot_read_domain_settings():
    admin, _email = _register("Globex")
    invited = admin.post(
        "/api/v1/organizations/invites",
        json={"email": f"emp-{uuid4().hex[:8]}@example.com", "role": "employee", "departments": []},
    )
    assert invited.status_code == 201
    employee = TestClient(app)
    registered = employee.post(
        "/api/v1/auth/register",
        json=register_payload(invited.json()["email"], invite_token=invited.json()["invite_token"]),
    )
    assert registered.status_code == 201
    assert employee.get("/api/v1/organizations/domain").status_code == 403


def test_unverified_custom_hostname_does_not_bind():
    globex, _email = _register("Globex")
    _enterprise(globex)
    put = globex.put("/api/v1/organizations/domain", json={"hostname": "kb.globex.example"})
    assert put.status_code == 200
    assert put.json()["custom_hostname"] == "kb.globex.example"
    assert put.json()["custom_verified"] is False
    token = put.json()["verification_token"]
    assert token

    db = SessionLocal()
    assert resolve_bound_organization(db, "kb.globex.example") is None
    db.close()

    me = globex.get("/api/v1/auth/me", headers={"Host": "kb.globex.example"})
    assert me.status_code == 200

    verified = globex.post("/api/v1/organizations/domain/verify", json={"token": token})
    assert verified.status_code == 200
    assert verified.json()["custom_verified"] is True
    assert verified.json()["verification_token"] is None

    db = SessionLocal()
    bound = resolve_bound_organization(db, "kb.globex.example")
    assert bound is not None
    assert bound.id == _org_id(globex)
    db.close()


def test_hostname_unique_across_orgs():
    acme, _a = _register("Acme")
    globex, _g = _register("Globex")
    _enterprise(acme)
    _enterprise(globex)
    assert acme.put("/api/v1/organizations/domain", json={"hostname": "shared.docs.example"}).status_code == 200
    taken = globex.put("/api/v1/organizations/domain", json={"hostname": "shared.docs.example"})
    assert taken.status_code == 409
    assert taken.json()["detail"] == HOSTNAME_IN_USE
    assert "acme" not in taken.text.lower()


def test_put_domain_foreign_organization_id_is_404():
    globex, _email = _register("Globex")
    acme, _other = _register("Acme")
    _enterprise(globex)
    response = globex.put(
        "/api/v1/organizations/domain",
        json={"hostname": "kb.globex.example", "organization_id": str(_org_id(acme))},
    )
    assert response.status_code == 404
    assert "acme" not in response.text.lower()


def test_platform_host_pins_session_and_blocks_switch():
    acme, acme_email = _register("Acme")
    globex, globex_email = _register("Globex")
    acme_org = _org_id(acme)
    globex_org = _org_id(globex)
    invited = acme.post(
        "/api/v1/organizations/invites",
        json={"email": globex_email, "role": "employee", "departments": []},
    )
    assert invited.status_code == 201
    switched = globex.post("/api/v1/auth/switch-organization", json={"organization_id": str(acme_org)})
    assert switched.status_code == 200
    assert UUID(switched.json()["organization_id"]) == acme_org

    slug = _slug_for(acme)
    before = globex.cookies.get(ACCESS_COOKIE)
    blocked = globex.post(
        "/api/v1/auth/switch-organization",
        json={"organization_id": str(globex_org)},
        headers=_host(slug),
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == HOST_SWITCH_DENIED
    assert globex.cookies.get(ACCESS_COOKIE) == before
    me = globex.get("/api/v1/auth/me", headers=_host(slug))
    assert me.status_code == 200
    assert UUID(me.json()["organization_id"]) == acme_org
    assert acme_email != globex_email


def test_acme_host_rejects_globex_session_on_raw():
    acme, _a = _register("Acme")
    globex, _g = _register("Globex")
    globex_org = _org_id(globex)
    db = SessionLocal()
    doc = Document(
        organization_id=globex_org,
        title="GlobexSecret.pdf",
        file_path=f"{uuid4()}/GlobexSecret.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=12,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    db.add(doc)
    db.commit()
    doc_id = doc.id
    db.close()

    slug = _slug_for(acme)
    raw = globex.get(f"/api/v1/documents/{doc_id}/raw", headers=_host(slug))
    assert raw.status_code == 401
    assert "GlobexSecret.pdf" not in raw.text
    me = globex.get("/api/v1/auth/me", headers=_host(slug))
    assert me.status_code == 401


def test_host_pin_does_not_replace_sql_org_filter():
    acme, _a = _register("Acme")
    globex, _g = _register("Globex")
    globex_org = _org_id(globex)
    db = SessionLocal()
    doc = Document(
        organization_id=globex_org,
        title="GlobexAll.pdf",
        file_path=f"{uuid4()}/GlobexAll.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=12,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    db.add(doc)
    db.commit()
    doc_id = doc.id
    db.close()

    slug = _slug_for(acme)
    raw = acme.get(f"/api/v1/documents/{doc_id}/raw", headers=_host(slug))
    assert raw.status_code == 404
    assert raw.json()["detail"] == "Document not found"
    assert "GlobexAll.pdf" not in raw.text


def test_login_on_acme_host_lands_in_acme_not_globex():
    globex, shared_email = _register("Globex", password="securepass123")
    acme, _ignore = _register("Acme")
    acme_org = _org_id(acme)
    globex_org = _org_id(globex)
    invited = acme.post(
        "/api/v1/organizations/invites",
        json={"email": shared_email, "role": "employee", "departments": []},
    )
    assert invited.status_code == 201
    slug = _slug_for(acme)
    guest = TestClient(app)
    unpinned = guest.post(
        "/api/v1/auth/login",
        json={"email": shared_email, "password": "securepass123"},
    )
    assert unpinned.status_code == 200
    assert UUID(unpinned.json()["organization_id"]) == globex_org
    guest = TestClient(app)
    logged = guest.post(
        "/api/v1/auth/login",
        json={"email": shared_email, "password": "securepass123"},
        headers=_host(slug),
    )
    assert logged.status_code == 200
    assert UUID(logged.json()["organization_id"]) == acme_org
    assert UUID(logged.json()["organization_id"]) != globex_org


def test_register_new_org_on_pinned_host_is_denied():
    acme, _email = _register("Acme")
    slug = _slug_for(acme)
    guest = TestClient(app)
    created = guest.post(
        "/api/v1/auth/register",
        json=register_payload(f"other-{uuid4().hex[:8]}@example.com", organization_name="OtherCo"),
        headers=_host(slug),
    )
    assert created.status_code == 403
    assert "Cannot create an organization on this host" in created.json()["detail"]


def test_csrf_allows_verified_custom_origin(monkeypatch):
    http, _email = _register("Acme")
    _enterprise(http)
    put = http.put("/api/v1/organizations/domain", json={"hostname": "kb.acme.example"})
    assert put.status_code == 200
    token = put.json()["verification_token"]
    assert http.post("/api/v1/organizations/domain/verify", json={"token": token}).status_code == 200
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    get_settings.cache_clear()
    try:
        allowed = http.post(
            "/api/v1/auth/logout",
            headers={"Origin": "https://kb.acme.example"},
        )
        assert allowed.status_code == 204
        db = SessionLocal()
        assert hostname_is_bound(db, "kb.acme.example")
        assert origin_allowed("https://kb.acme.example")
        db.close()
    finally:
        get_settings.cache_clear()


def test_csrf_rejects_unverified_origin_as_allowlist(monkeypatch):
    http, _email = _register("Acme")
    _enterprise(http)
    assert http.put("/api/v1/organizations/domain", json={"hostname": "pending.acme.example"}).status_code == 200
    monkeypatch.setenv("COOKIE_SAMESITE", "none")
    get_settings.cache_clear()
    try:
        blocked = http.post(
            "/api/v1/auth/logout",
            headers={"Origin": "https://pending.acme.example"},
        )
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == "CSRF check failed"
    finally:
        get_settings.cache_clear()


def test_nested_localhost_origin_is_allowed_for_cors_preflight():
    origin = "http://bootorg.docwise.app.localhost:3001"
    assert origin_allowed(origin)
    http = TestClient(app)
    preflight = http.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-requested-with",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == origin


def test_compose_localhost_alias_pins_verified_custom():
    acme, _a = _register("Acme")
    globex, _g = _register("Globex")
    _enterprise(acme)
    put = acme.put("/api/v1/organizations/domain", json={"hostname": "bootorg.docwise.app"})
    assert put.status_code == 200
    token = put.json()["verification_token"]
    assert acme.post("/api/v1/organizations/domain/verify", json={"token": token}).status_code == 200
    db = SessionLocal()
    pinned = resolve_bound_organization(db, "bootorg.docwise.app.localhost")
    db.close()
    assert pinned is not None
    assert pinned.id == _org_id(acme)
    raw = globex.get(
        "/api/v1/auth/me",
        headers={"Host": "bootorg.docwise.app.localhost"},
    )
    assert raw.status_code == 401
