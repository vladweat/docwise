"""Two organizations on one Postgres: no list/raw/retrieval/prompt/cache leaks."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM, make_chunk_id
from app.models.user import UserRole
from app.services.chat import cache_key
from helpers import register_payload, wipe_app_tables
from pdf_fixtures import tagged_pdf_bytes


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        from app.services.storage import StorageError

        if key not in self.objects:
            raise StorageError("missing")
        return self.objects[key]

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


def _pdf(tag: str) -> bytes:
    return tagged_pdf_bytes(tag)


def _vec(seed: int) -> list[float]:
    return [((seed + offset) % 17) / 17.0 for offset in range(EMBEDDING_DIM)]


@pytest.fixture(autouse=True)
def clean_tables():
    db: Session = SessionLocal()
    wipe_app_tables(db)
    db.close()
    yield
    db = SessionLocal()
    wipe_app_tables(db)
    db.close()


@pytest.fixture
def storage():
    from app.api.v1.documents import get_storage

    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture(autouse=True)
def _mock_celery(monkeypatch):
    monkeypatch.setattr("app.services.documents.enqueue_ingestion", lambda document_id: None)


def _register(name: str) -> TestClient:
    http = TestClient(app)
    email = f"{name}-{uuid4().hex[:8]}@example.com"
    response = http.post(
        "/api/v1/auth/register",
        json=register_payload(email, organization_name=name),
    )
    assert response.status_code == 201
    return http


def _invite(admin: TestClient, *, role: str, departments: list[str] | None = None) -> TestClient:
    email = f"member-{uuid4().hex[:8]}@example.com"
    invited = admin.post(
        "/api/v1/organizations/invites",
        json={"email": email, "role": role, "departments": departments or []},
    )
    assert invited.status_code == 201
    http = TestClient(app)
    response = http.post(
        "/api/v1/auth/register",
        json=register_payload(email, invite_token=invited.json()["invite_token"]),
    )
    assert response.status_code == 201
    return http


def test_two_orgs_same_all_tag_do_not_leak_list_or_raw(storage: FakeStorage):
    acme = _register("Acme")
    globex = _register("Globex")
    content = _pdf("acme-all")
    uploaded = acme.post(
        "/api/v1/documents/upload",
        files={"file": ("Handbook.pdf", content, "application/pdf")},
        data={"access_roles": "all"},
    )
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["id"]
    assert uploaded.json()["title"] == "Handbook.pdf"

    listed = globex.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["total"] == 0
    assert "Handbook.pdf" not in listed.text
    assert doc_id not in listed.text

    raw = globex.get(f"/api/v1/documents/{doc_id}/raw")
    assert raw.status_code == 404
    assert raw.json()["detail"] == "Document not found"
    assert "Handbook.pdf" not in raw.text

    status_resp = globex.get(f"/api/v1/documents/{doc_id}/status")
    assert status_resp.status_code == 404

    duplicate = globex.post(
        "/api/v1/documents/upload",
        files={"file": ("Copy.pdf", content, "application/pdf")},
        data={"access_roles": "all"},
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] != doc_id


def test_invite_existing_user_adds_membership_not_global_role(storage: FakeStorage):
    acme = _register("Acme")
    globex = _register("Globex")
    globex_email = globex.get("/api/v1/auth/me").json()["email"]
    invited = acme.post(
        "/api/v1/organizations/invites",
        json={"email": globex_email, "role": "employee", "departments": ["hr"]},
    )
    assert invited.status_code == 201
    assert invited.json()["status"] == "added"
    assert invited.json()["invite_token"] is None

    acme_org = UUID(acme.get("/api/v1/auth/me").json()["organization_id"])
    switched = globex.post(
        "/api/v1/auth/switch-organization",
        json={"organization_id": str(acme_org)},
    )
    assert switched.status_code == 200
    body = switched.json()
    assert body["role"] == "employee"
    assert body["departments"] == ["hr"]
    assert UUID(body["organization_id"]) == acme_org

    foreign = globex.post("/api/v1/auth/switch-organization", json={"organization_id": str(uuid4())})
    assert foreign.status_code == 404
    assert "acme" not in foreign.text.lower()
    assert "globex" not in foreign.text.lower()


def test_client_organization_id_in_body_is_ignored(storage: FakeStorage, monkeypatch):
    from app.core.config import get_settings
    from app.services.retrieval import RetrievalResult

    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    seen: list[UUID] = []

    def fake_retrieve(_db, user, _query, **_kwargs):
        seen.append(user.organization_id)
        return RetrievalResult(chunks=[], allowed_roles=tuple(user.allowed_roles()))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    acme = _register("Acme")
    globex = _register("Globex")
    globex_org = UUID(globex.get("/api/v1/auth/me").json()["organization_id"])
    acme_org = UUID(acme.get("/api/v1/auth/me").json()["organization_id"])
    response = acme.post(
        "/api/v1/chat/stream",
        json={"query": f"ignore org {uuid4().hex}", "organization_id": str(globex_org)},
    )
    assert response.status_code == 200
    assert seen == [acme_org]
    get_settings.cache_clear()


def test_retrieval_and_cache_do_not_cross_orgs(monkeypatch):
    from app.core.config import get_settings
    from app.services.chat.llm import LLMUsage
    from app.services.retrieval import RetrievedChunk, RetrievalResult

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    question = f"What is the travel cap {uuid4().hex}?"
    public = RetrievedChunk(
        id=uuid4(),
        document_id=uuid4(),
        chunk_id="doc:1:0",
        doc_title="AcmeHandbook.pdf",
        page_number=1,
        content="Acme travel cap is 150 USD.",
        access_roles=("all",),
        score=0.9,
    )
    calls = {"stream": 0}

    def fake_retrieve(_db, user, _query, **_kwargs):
        if user.organization_name == "Acme":
            return RetrievalResult(chunks=[public], allowed_roles=tuple(user.allowed_roles()))
        return RetrievalResult(chunks=[], allowed_roles=tuple(user.allowed_roles()))

    def fake_stream(messages, **_kwargs):
        calls["stream"] += 1
        joined = " ".join(item["content"] for item in messages)
        assert "Acme travel cap" in joined
        yield "Acme travel cap is 150 USD [AcmeHandbook.pdf, p. 1]."
        yield LLMUsage(tokens_used=8)

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    acme = _register("Acme")
    globex = _register("Globex")
    acme_resp = acme.post("/api/v1/chat/stream", json={"query": question})
    assert acme_resp.status_code == 200
    assert "AcmeHandbook.pdf" in acme_resp.text

    globex_resp = globex.post("/api/v1/chat/stream", json={"query": question})
    assert globex_resp.status_code == 200
    assert "AcmeHandbook.pdf" not in globex_resp.text
    assert "150 USD" not in globex_resp.text
    assert calls["stream"] == 1

    acme_id = UUID(acme.get("/api/v1/auth/me").json()["organization_id"])
    globex_id = UUID(globex.get("/api/v1/auth/me").json()["organization_id"])
    assert cache_key(question, ["admin", "all"], organization_id=acme_id) != cache_key(
        question, ["admin", "all"], organization_id=globex_id
    )
    get_settings.cache_clear()


def test_dense_search_filters_other_org_all_chunks(db_session_unused=None):
    from app.services.retrieval import dense_search

    acme = _register("Acme")
    globex = _register("Globex")
    acme_org = UUID(acme.get("/api/v1/auth/me").json()["organization_id"])
    globex_org = UUID(globex.get("/api/v1/auth/me").json()["organization_id"])
    db = SessionLocal()
    secret = Document(
        organization_id=globex_org,
        title="GlobexAll.pdf",
        file_path=f"{uuid4()}/GlobexAll.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=12,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    db.add(secret)
    db.flush()
    vec = _vec(2)
    db.add(
        DocumentChunk(
            document_id=secret.id,
            organization_id=globex_org,
            chunk_id=make_chunk_id(secret.id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="Globex secret policy text.",
            token_count=4,
            embedding=vec,
            doc_title=secret.title,
        )
    )
    db.commit()
    hits = dense_search(db, vec, ["all", "employee", "admin"], organization_id=acme_org, limit=10)
    titles = {chunk.doc_title for chunk, _dist in hits}
    assert "GlobexAll.pdf" not in titles
    db.close()


def test_members_and_invites_are_org_admin_only():
    acme = _register("Acme")
    employee = _invite(acme, role=UserRole.employee.value)
    denied = employee.get("/api/v1/organizations/members")
    assert denied.status_code == 403
    members = acme.get("/api/v1/organizations/members")
    assert members.status_code == 200
    emails = {item["email"] for item in members.json()["items"]}
    assert employee.get("/api/v1/auth/me").json()["email"] in emails
    assert members.json()["total"] == 2
