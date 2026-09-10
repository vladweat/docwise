"""M6a: plan defaults, org quotas (402), billing reads. No live Stripe."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.documents import get_storage
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.chat import RagAuditLog
from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id
from app.models.organization import Organization, OrganizationPlan
from app.services.ingestion import IndexResult, run_ingestion
from app.services.quotas import QUOTA_EXCEEDED
from helpers import make_org, register_payload, wipe_app_tables

MIN_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        from app.services.storage import StorageError

        if key not in self.objects:
            raise StorageError("missing")
        return self.objects[key]

    def delete_object(self, key: str) -> None:
        self.deleted.append(key)
        self.objects.pop(key, None)


def _pdf(tag: str) -> bytes:
    return MIN_PDF.replace(b"%%EOF", f"%{tag}\n%%EOF".encode())


def _unique_email(prefix: str = "quota") -> str:
    return f"{prefix}-{uuid4().hex[:8]}@example.com"


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
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture(autouse=True)
def _mock_celery(monkeypatch):
    monkeypatch.setattr("app.services.document_service.enqueue_ingestion", lambda document_id: None)


def _tight_starter_pages(monkeypatch, pages: int) -> None:
    monkeypatch.setenv("PLAN_STARTER_PAGES", str(pages))
    get_settings.cache_clear()


def _tight_starter_seats(monkeypatch, seats: int) -> None:
    monkeypatch.setenv("PLAN_STARTER_SEATS", str(seats))
    get_settings.cache_clear()


def _tight_starter_tokens(monkeypatch, tokens: int) -> None:
    monkeypatch.setenv("PLAN_STARTER_TOKENS", str(tokens))
    get_settings.cache_clear()


def _register(name: str) -> TestClient:
    http = TestClient(app)
    email = _unique_email(name.lower().replace(" ", ""))
    response = http.post(
        "/api/v1/auth/register",
        json=register_payload(email, organization_name=name),
    )
    assert response.status_code == 201
    return http


def _org_id(http: TestClient) -> UUID:
    return UUID(http.get("/api/v1/auth/me").json()["organization_id"])


def _user_id(http: TestClient) -> UUID:
    return UUID(http.get("/api/v1/auth/me").json()["id"])


def _seed_indexed_pages(org_id: UUID, pages: int) -> None:
    db = SessionLocal()
    doc = Document(
        organization_id=org_id,
        title="Existing.pdf",
        file_path=f"orgs/{org_id}/{uuid4()}/Existing.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=12,
        total_pages=pages,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    db.add(doc)
    db.commit()
    db.close()


def _upload(http: TestClient, tag: str, roles: list[str] | None = None):
    return http.post(
        "/api/v1/documents/upload",
        files={"file": (f"{tag}.pdf", _pdf(tag), "application/pdf")},
        data={"access_roles": roles or ["all"]},
    )


def _parse_sse(body: str) -> list[dict | str]:
    events: list[dict | str] = []
    for block in body.split("\n\n"):
        line = next((part for part in block.split("\n") if part.startswith("data: ")), None)
        if not line:
            continue
        payload = line[6:]
        if payload == "[DONE]":
            events.append("[DONE]")
            continue
        events.append(json.loads(payload))
    return events


def test_new_organization_is_starter():
    http = _register("Acme")
    db = SessionLocal()
    org = db.get(Organization, _org_id(http))
    assert org is not None
    assert org.plan == OrganizationPlan.starter.value
    assert org.billing_status == "active"
    assert org.current_period_start is not None
    assert org.current_period_end is not None
    assert org.current_period_end > org.current_period_start
    db.close()


def test_admin_billing_usage_and_subscription_are_current_org_only():
    acme = _register("Acme")
    globex = _register("Globex")
    acme_org = _org_id(acme)
    _seed_indexed_pages(acme_org, 7)
    _seed_indexed_pages(_org_id(globex), 99)

    usage = acme.get("/api/v1/billing/usage")
    assert usage.status_code == 200
    body = usage.json()
    assert body["plan"] == "starter"
    assert body["pages"]["used"] == 7
    assert body["pages"]["limit"] >= body["pages"]["used"]
    assert body["seats"]["used"] == 1
    assert "99" not in json.dumps(body)

    sub = acme.get("/api/v1/billing/subscription")
    assert sub.status_code == 200
    assert sub.json()["plan"] == "starter"
    assert sub.json()["entitlements"]["sso"] is False
    assert sub.json()["billing_status"] == "active"
    assert sub.json()["provider"] == "dev"

    other = globex.get("/api/v1/billing/usage")
    assert other.json()["pages"]["used"] == 99


def test_employee_cannot_read_billing():
    admin = _register("Acme")
    email = _unique_email("emp")
    invited = admin.post(
        "/api/v1/organizations/invites",
        json={"email": email, "role": "employee", "departments": []},
    )
    assert invited.status_code == 201
    employee = TestClient(app)
    registered = employee.post(
        "/api/v1/auth/register",
        json=register_payload(email, invite_token=invited.json()["invite_token"]),
    )
    assert registered.status_code == 201
    for path in ("/api/v1/billing/usage", "/api/v1/billing/subscription"):
        response = employee.get(path)
        assert response.status_code == 403
        assert "usage" not in response.json()["detail"].lower()
        assert "quota" not in response.json()["detail"].lower()


def test_page_quota_402_only_hits_capped_org(storage: FakeStorage, monkeypatch):
    _tight_starter_pages(monkeypatch, 10)
    acme = _register("Acme")
    globex = _register("Globex")
    _seed_indexed_pages(_org_id(acme), 10)

    queued: list[str] = []
    monkeypatch.setattr(
        "app.services.document_service.enqueue_ingestion",
        lambda document_id: queued.append(str(document_id)),
    )

    blocked = _upload(acme, "over-cap")
    assert blocked.status_code == 402
    assert blocked.json()["detail"] == QUOTA_EXCEEDED
    assert "Existing.pdf" not in blocked.text
    assert queued == []
    assert storage.objects == {}

    allowed = _upload(globex, "globex-ok")
    assert allowed.status_code == 201
    assert allowed.json()["status"] == "pending"
    assert queued == [allowed.json()["id"]]


def test_upload_402_does_not_confirm_other_org_file(storage: FakeStorage, monkeypatch):
    _tight_starter_pages(monkeypatch, 1)
    acme = _register("Acme")
    globex = _register("Globex")
    secret_hash = "ab" * 32
    db = SessionLocal()
    db.add(
        Document(
            organization_id=_org_id(globex),
            title="Secret-Globex.pdf",
            file_path="hidden.pdf",
            file_hash=secret_hash,
            file_size_bytes=8,
            total_pages=1,
            access_roles=["all"],
            status=DocumentStatus.ready.value,
        )
    )
    db.add(
        Document(
            organization_id=_org_id(acme),
            title="Acme-full.pdf",
            file_path="full.pdf",
            file_hash="cd" * 32,
            file_size_bytes=8,
            total_pages=1,
            access_roles=["hr"],
            status=DocumentStatus.ready.value,
        )
    )
    db.commit()
    db.close()

    blocked = _upload(acme, "another")
    assert blocked.status_code == 402
    assert blocked.json()["detail"] == QUOTA_EXCEEDED
    assert "Secret-Globex" not in blocked.text
    assert "Acme-full" not in blocked.text
    assert secret_hash not in blocked.text


def test_invite_402_when_seats_exhausted(monkeypatch):
    _tight_starter_seats(monkeypatch, 1)
    admin = _register("Acme")
    response = admin.post(
        "/api/v1/organizations/invites",
        json={"email": _unique_email("seat"), "role": "employee", "departments": []},
    )
    assert response.status_code == 402
    assert response.json()["detail"] == QUOTA_EXCEEDED


def test_existing_user_invite_402_at_seat_cap(monkeypatch):
    _tight_starter_seats(monkeypatch, 1)
    acme = _register("Acme")
    globex = _register("Globex")
    globex_email = globex.get("/api/v1/auth/me").json()["email"]
    response = acme.post(
        "/api/v1/organizations/invites",
        json={"email": globex_email, "role": "employee", "departments": []},
    )
    assert response.status_code == 402
    assert response.json()["detail"] == QUOTA_EXCEEDED
    me = globex.get("/api/v1/auth/me").json()
    assert len(me["organizations"]) == 1


def test_chat_token_quota_errors_before_retrieval(monkeypatch):
    _tight_starter_tokens(monkeypatch, 10)
    http = _register("Acme")
    db = SessionLocal()
    db.add(
        RagAuditLog(
            organization_id=_org_id(http),
            user_id=_user_id(http),
            query="prior",
            retrieved_chunk_ids=[],
            tokens_used=10,
        )
    )
    db.commit()
    db.close()

    called = {"retrieve": 0}

    def fake_retrieve(*_args, **_kwargs):
        called["retrieve"] += 1
        raise AssertionError("retrieval must not run when token quota is exhausted")

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)

    def boom_cache(*_args, **_kwargs):
        raise AssertionError("cache must not run")

    monkeypatch.setattr("app.services.chat.load_cached_answer", boom_cache)

    response = http.post("/api/v1/chat/stream", json={"query": "What is the travel cap?"})
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events[0]["type"] == "error"
    assert events[0]["content"] == QUOTA_EXCEEDED
    assert events[-1] == "[DONE]"
    assert called["retrieve"] == 0
    assert "chunk" not in json.dumps(events).lower()


def test_ingest_over_page_cap_fails_without_ready(storage: FakeStorage, monkeypatch):
    _tight_starter_pages(monkeypatch, 3)
    db = SessionLocal()
    org = make_org(db)
    document_id = uuid4()
    key = f"orgs/{org.id}/{document_id}/Over.pdf"
    storage.objects[key] = MIN_PDF
    document = Document(
        id=document_id,
        organization_id=org.id,
        title="Over.pdf",
        file_path=key,
        file_hash=uuid4().hex,
        file_size_bytes=len(MIN_PDF),
        access_roles=["all"],
        status=DocumentStatus.pending.value,
    )
    db.add(document)
    db.commit()

    def index_too_many(session: Session, doc: Document, pdf_bytes: bytes) -> IndexResult:
        session.add(
            DocumentChunk(
                document_id=doc.id,
                organization_id=doc.organization_id,
                chunk_id=make_chunk_id(doc.id, 1, 0),
                page_number=1,
                access_roles=list(doc.access_roles),
                content="should be rolled back",
                token_count=1,
                doc_title=doc.title,
            )
        )
        return IndexResult(chunk_count=1, total_pages=4)

    monkeypatch.setattr("app.services.ingestion.acquire_indexing_lock", lambda *_a, **_k: True)
    monkeypatch.setattr("app.services.ingestion.release_indexing_lock", lambda *_a, **_k: None)

    result = run_ingestion(db, document_id, storage=storage, index_fn=index_too_many)
    assert result["status"] == "failed"
    db.expire_all()
    stored = db.get(Document, document_id)
    assert stored is not None
    assert stored.status == DocumentStatus.failed.value
    assert stored.last_error == QUOTA_EXCEEDED
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    assert chunks == 0
    assert key not in storage.objects
    assert key in storage.deleted
    db.close()


def test_failed_pages_do_not_count_toward_upload_cap(storage: FakeStorage, monkeypatch):
    _tight_starter_pages(monkeypatch, 5)
    http = _register("Acme")
    db = SessionLocal()
    db.add(
        Document(
            organization_id=_org_id(http),
            title="Broken.pdf",
            file_path="broken.pdf",
            file_hash="ef" * 32,
            file_size_bytes=4,
            total_pages=40,
            access_roles=["all"],
            status=DocumentStatus.failed.value,
        )
    )
    db.commit()
    db.close()
    response = _upload(http, "still-ok")
    assert response.status_code == 201
