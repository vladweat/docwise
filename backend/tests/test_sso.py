"""M6c: SSO_PROVIDER=dev. Org from connector slug, not the assertion."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth_cookies import ACCESS_COOKIE
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM, make_chunk_id
from app.models.organization import Organization, OrganizationMembership
from app.models.user import User, UserRole
from app.services.retrieval import dense_search
from app.services.org.sso import SSO_NOT_IN_PLAN, SSO_REQUIRED
from helpers import api_error_message, register_payload, set_org_plan, wipe_app_tables

SSO_JSON = {"X-Requested-With": "Docwise", "Accept": "application/json"}


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


def _put_sso(http: TestClient, **overrides) -> dict:
    body = {
        "protocol": "saml",
        "idp_entity_id": "https://idp.example/metadata",
        "idp_metadata": {"kind": "dev"},
        "jit_enabled": True,
        "attribute_map": {
            "default_role": "employee",
            "default_departments": [],
            "rules": [
                {"group": "admins", "role": "admin", "departments": ["engineering"]},
                {"group": "hr-team", "role": "manager", "departments": ["hr"]},
            ],
        },
        "sso_enforced": False,
    }
    body.update(overrides)
    response = http.put("/api/v1/organizations/sso", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _acs(http: TestClient, slug: str, email: str, **assertion) -> object:
    payload = {"email": email, "email_verified": True, "groups": [], **assertion}
    return http.post(f"/api/v1/auth/sso/{slug}/acs", json=payload, headers=SSO_JSON)


def test_starter_cannot_upsert_sso_connector():
    http, _email = _register("Acme")
    response = http.put(
        "/api/v1/organizations/sso",
        json={"jit_enabled": True, "sso_enforced": False},
    )
    assert response.status_code == 403
    assert api_error_message(response) == SSO_NOT_IN_PLAN
    assert "idp" not in api_error_message(response).lower()
    assert http.get("/api/v1/organizations/sso").status_code == 403


def test_employee_cannot_read_sso_settings():
    admin, _email = _register("Globex")
    _enterprise(admin)
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
    assert employee.get("/api/v1/organizations/sso").status_code == 403


def test_enterprise_upsert_and_sp_initiated_login():
    http, _email = _register("Globex")
    _enterprise(http)
    configured = _put_sso(http)
    assert configured["configured"] is True
    assert configured["provider"] == "dev"
    slug = configured["slug"]
    login = http.get(f"/api/v1/auth/sso/{slug}/login", follow_redirects=False)
    assert login.status_code == 302
    assert slug in login.headers["location"]
    missing = http.get("/api/v1/auth/sso/no-such-org/login", follow_redirects=False)
    assert missing.status_code == 404
    assert api_error_message(missing) == "Not found"


def test_acs_uses_connector_org_not_assertion_body():
    acme, _acme_email = _register("Acme")
    globex, globex_email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex)["slug"]
    acme_org = str(_org_id(acme))
    globex_org = str(_org_id(globex))
    guest = TestClient(app)
    response = _acs(
        guest,
        slug,
        globex_email,
        organization_id=acme_org,
        org_id=acme_org,
        groups=["admins"],
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" not in body
    assert body["organization_id"] == globex_org
    assert body["organization_name"] == "Globex"
    assert body["role"] == "admin"
    assert "engineering" in body["departments"]
    me = guest.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["organization_id"] == globex_org


def test_acs_sets_cookies_on_redirect_and_ignores_bearer():
    globex, globex_email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex)["slug"]
    globex_org = str(_org_id(globex))
    bearer = create_access_token("stranger@example.com", org_id=globex_org)
    guest = TestClient(app)
    response = guest.post(
        f"/api/v1/auth/sso/{slug}/acs",
        json={"email": globex_email, "email_verified": True, "groups": []},
        headers={"Authorization": f"Bearer {bearer}"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert ACCESS_COOKIE in response.cookies
    me = guest.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == globex_email
    other = TestClient(app)
    denied = other.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bearer}"})
    assert denied.status_code == 401


def test_unverified_email_is_rejected():
    globex, _email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex)["slug"]
    guest = TestClient(app)
    response = _acs(guest, slug, "sso-user@example.com", email_verified=False)
    assert response.status_code == 401


def test_jit_only_adds_membership_in_connector_org():
    acme, acme_email = _register("Acme")
    globex, _globex_email = _register("Globex")
    acme_org = _org_id(acme)
    globex_org = _org_id(globex)
    _enterprise(globex)
    slug = _put_sso(globex, jit_enabled=True)["slug"]
    guest = TestClient(app)
    response = _acs(guest, slug, acme_email, groups=["hr-team"])
    assert response.status_code == 200
    body = response.json()
    assert UUID(body["organization_id"]) == globex_org
    assert body["role"] == "manager"
    assert body["departments"] == ["hr"]
    db = SessionLocal()
    user = db.query(User).filter(User.email == acme_email).first()
    assert user is not None
    acme_m = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == acme_org,
        )
        .one()
    )
    globex_m = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.organization_id == globex_org,
        )
        .one()
    )
    assert acme_m.role == UserRole.admin.value
    assert globex_m.role == UserRole.manager.value
    assert globex_m.departments == ["hr"]
    db.close()


def test_without_jit_requires_invite():
    globex, _email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex, jit_enabled=False)["slug"]
    guest = TestClient(app)
    denied = _acs(guest, slug, f"stranger-{uuid4().hex[:8]}@example.com")
    assert denied.status_code == 403
    invited_email = f"invited-{uuid4().hex[:8]}@example.com"
    invite = globex.post(
        "/api/v1/organizations/invites",
        json={"email": invited_email, "role": "employee", "departments": ["finance"]},
    )
    assert invite.status_code == 201
    accepted = _acs(guest, slug, invited_email)
    assert accepted.status_code == 200
    assert accepted.json()["role"] == "employee"
    assert accepted.json()["departments"] == ["finance"]


def test_sso_enforced_blocks_password_google_and_switch(monkeypatch):
    acme, shared_email = _register("Acme")
    password = "securepass123"
    globex, _ignore = _register("Globex")
    globex_org = _org_id(globex)
    _enterprise(globex)
    slug = _slug_for(globex)
    _put_sso(globex, sso_enforced=False, jit_enabled=True)
    invited = globex.post(
        "/api/v1/organizations/invites",
        json={"email": shared_email, "role": "employee", "departments": []},
    )
    assert invited.status_code == 201
    _put_sso(globex, sso_enforced=True, jit_enabled=True)

    login_client = TestClient(app)
    logged = login_client.post("/api/v1/auth/login", json={"email": shared_email, "password": password})
    assert logged.status_code == 200
    assert logged.json()["organization_name"] == "Acme"
    blocked = login_client.post("/api/v1/auth/switch-organization", json={"organization_id": str(globex_org)})
    assert blocked.status_code == 403
    assert api_error_message(blocked) == SSO_REQUIRED

    fresh = TestClient(app)
    assert _acs(fresh, slug, shared_email).status_code == 200
    switched = fresh.post("/api/v1/auth/switch-organization", json={"organization_id": str(_org_id(acme))})
    assert switched.status_code == 200
    back = fresh.post("/api/v1/auth/switch-organization", json={"organization_id": str(globex_org)})
    assert back.status_code == 200
    assert back.json()["organization_id"] == str(globex_org)

    google_sub = f"google-{uuid4().hex[:8]}"

    def fake_verify(token: str, client_id: str) -> dict:
        return {"sub": google_sub, "email": shared_email, "email_verified": True}

    from app.core.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.v1.auth.verify_google_id_token", fake_verify)
    google_client = TestClient(app)
    google = google_client.post("/api/v1/auth/google", json={"id_token": "valid-token"})
    assert google.status_code == 200
    assert google.json()["organization_name"] == "Acme"
    get_settings.cache_clear()


def test_sso_enforced_rejects_password_cookie_without_sso_claim():
    globex, email = _register("Globex")
    _enterprise(globex)
    org_id = str(_org_id(globex))
    _put_sso(globex, sso_enforced=True)
    token = create_access_token(email, org_id=org_id)
    guest = TestClient(app)
    guest.cookies.set(ACCESS_COOKIE, token)
    me = guest.get("/api/v1/auth/me")
    assert me.status_code == 401


def test_group_mapping_does_not_write_document_access_roles():
    globex, _email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex, jit_enabled=True)["slug"]
    db = SessionLocal()
    org_id = _org_id(globex)
    doc = Document(
        organization_id=org_id,
        title="Policy.pdf",
        file_path=f"{uuid4()}/Policy.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=12,
        access_roles=["admin"],
        status=DocumentStatus.ready.value,
    )
    db.add(doc)
    db.commit()
    doc_id = doc.id
    db.close()
    guest = TestClient(app)
    assert _acs(guest, slug, f"hr-{uuid4().hex[:8]}@example.com", groups=["hr-team"]).status_code == 200
    db = SessionLocal()
    loaded = db.get(Document, doc_id)
    assert loaded is not None
    assert list(loaded.access_roles) == ["admin"]
    db.close()


def test_plan_without_sso_hides_connector_as_not_found():
    globex, email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex)["slug"]
    db = SessionLocal()
    set_org_plan(db, _org_id(globex), "starter")
    db.close()
    guest = TestClient(app)
    login = guest.get(f"/api/v1/auth/sso/{slug}/login", follow_redirects=False)
    assert login.status_code == 404
    acs = _acs(guest, slug, email)
    assert acs.status_code == 404
    assert api_error_message(acs) == "Not found"


def test_sso_globex_cannot_list_or_raw_acme_all_document():
    acme, _acme_email = _register("Acme")
    globex, _globex_email = _register("Globex")
    _enterprise(globex)
    slug = _put_sso(globex, jit_enabled=True)["slug"]
    db = SessionLocal()
    acme_org = _org_id(acme)
    secret = Document(
        organization_id=acme_org,
        title="AcmeHandbook.pdf",
        file_path=f"{uuid4()}/AcmeHandbook.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=12,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    db.add(secret)
    db.flush()
    db.add(
        DocumentChunk(
            document_id=secret.id,
            organization_id=acme_org,
            chunk_id=make_chunk_id(secret.id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="Acme secret policy text.",
            token_count=4,
            embedding=[0.05] * EMBEDDING_DIM,
            doc_title=secret.title,
        )
    )
    db.commit()
    doc_id = secret.id
    db.close()
    sso_user = TestClient(app)
    sso_email = f"globex-{uuid4().hex[:8]}@example.com"
    assert _acs(sso_user, slug, sso_email).status_code == 200
    globex_org = UUID(sso_user.get("/api/v1/auth/me").json()["organization_id"])
    listed = sso_user.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert "AcmeHandbook.pdf" not in listed.text
    raw = sso_user.get(f"/api/v1/documents/{doc_id}/raw")
    assert raw.status_code == 404
    assert "AcmeHandbook.pdf" not in raw.text
    db = SessionLocal()
    hits = dense_search(
        db,
        [0.05] * EMBEDDING_DIM,
        ["all", "employee", "admin"],
        organization_id=globex_org,
        limit=10,
    )
    titles = {chunk.doc_title for chunk, _dist in hits}
    assert "AcmeHandbook.pdf" not in titles
    db.close()


def test_put_sso_foreign_organization_id_is_404():
    globex, _email = _register("Globex")
    acme, _other = _register("Acme")
    _enterprise(globex)
    response = globex.put(
        "/api/v1/organizations/sso",
        json={
            "jit_enabled": True,
            "sso_enforced": False,
            "organization_id": str(_org_id(acme)),
        },
    )
    assert response.status_code == 404
