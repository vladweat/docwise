from __future__ import annotations

import hashlib
import uuid
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.documents import get_storage
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id
from app.models.user import User, UserRole
from app.services.document_service import parse_access_roles
from app.services.storage import StorageError

MIN_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        if key not in self.objects:
            raise StorageError("missing")
        return self.objects[key]

    def delete_object(self, key: str) -> None:
        self.objects.pop(key, None)


def _pdf(tag: str) -> bytes:
    return MIN_PDF.replace(b"%%EOF", f"%{tag}\n%%EOF".encode())


def _unique_email() -> str:
    return f"docs-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def storage():
    fake = FakeStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_storage, None)


@pytest.fixture(autouse=True)
def _mock_celery(monkeypatch):
    monkeypatch.setattr("app.services.document_service.enqueue_ingestion", lambda document_id: None)


@pytest.fixture(autouse=True)
def clean_tables():
    db: Session = SessionLocal()
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield
    db = SessionLocal()
    db.query(DocumentChunk).delete()
    db.query(Document).delete()
    db.query(User).delete()
    db.commit()
    db.close()


@pytest.fixture
def admin_client() -> TestClient:
    client = TestClient(app)
    email = _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    return client


def _register_user(role: str, departments: list[str] | None = None) -> TestClient:
    client = TestClient(app)
    email = _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "securepass123"},
    )
    assert response.status_code == 201
    db = SessionLocal()
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    user.role = role
    user.departments = departments or []
    db.commit()
    db.close()
    return client


def _upload(
    client: TestClient,
    *,
    filename: str,
    content: bytes,
    roles: list[str] | str,
    content_type: str = "application/pdf",
):
    data = {"access_roles": roles}
    return client.post(
        "/api/v1/documents/upload",
        files={"file": (filename, content, content_type)},
        data=data,
    )


def test_parse_access_roles_json_and_repeated():
    assert parse_access_roles('["HR", "all"]') == ["hr", "all"]
    assert parse_access_roles(["finance", "finance", "all"]) == ["finance", "all"]
    assert parse_access_roles("hr, finance") == ["hr", "finance"]
    with pytest.raises(HTTPException) as exc:
        parse_access_roles([])
    assert exc.value.status_code == 400


def test_upload_returns_201_pending_and_enqueues(admin_client: TestClient, storage: FakeStorage, monkeypatch):
    enqueued: list[UUID] = []
    monkeypatch.setattr(
        "app.services.document_service.enqueue_ingestion",
        lambda document_id: enqueued.append(document_id),
    )
    content = _pdf("upload-ok")
    response = _upload(admin_client, filename="Policy.pdf", content=content, roles=["all", "hr"])
    assert response.status_code == 201
    body = response.json()
    UUID(body["id"])
    assert body["title"] == "Policy.pdf"
    assert body["status"] == "pending"
    assert body["access_roles"] == ["all", "hr"]
    assert body["file_size_bytes"] == len(content)
    assert body["total_pages"] is None
    assert enqueued == [UUID(body["id"])]
    assert any(key.endswith("/Policy.pdf") for key in storage.objects)
    db = SessionLocal()
    stored = db.get(Document, UUID(body["id"]))
    assert stored is not None
    assert stored.file_hash == hashlib.sha256(content).hexdigest()
    assert stored.status == DocumentStatus.pending.value
    db.close()


def test_duplicate_file_hash_returns_409_without_existing_payload(admin_client: TestClient, storage: FakeStorage):
    content = _pdf("dup")
    first = _upload(admin_client, filename="One.pdf", content=content, roles=["hr"])
    assert first.status_code == 201
    existing_id = first.json()["id"]
    second = _upload(admin_client, filename="Two.pdf", content=content, roles=["all"])
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail == "Document with this file hash already exists"
    assert existing_id not in detail
    assert "One.pdf" not in second.text
    db = SessionLocal()
    assert db.query(Document).count() == 1
    db.close()


def test_upload_rejects_non_pdf_and_oversize(admin_client: TestClient, storage: FakeStorage, monkeypatch):
    txt = _upload(admin_client, filename="notes.txt", content=MIN_PDF, roles=["all"])
    assert txt.status_code == 400
    bad_magic = _upload(admin_client, filename="fake.pdf", content=b"not a pdf", roles=["all"])
    assert bad_magic.status_code == 400
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "20")
    get_settings.cache_clear()
    huge = _upload(admin_client, filename="big.pdf", content=_pdf("huge") + b"x" * 50, roles=["all"])
    assert huge.status_code == 413
    get_settings.cache_clear()
    assert storage.objects == {}


def test_upload_requires_admin(storage: FakeStorage):
    TestClient(app).post(
        "/api/v1/auth/register",
        json={"email": _unique_email(), "password": "securepass123"},
    )
    employee = _register_user(UserRole.employee.value)
    response = _upload(employee, filename="Policy.pdf", content=_pdf("emp"), roles=["all"])
    assert response.status_code == 403

    manager = _register_user(UserRole.manager.value)
    response = _upload(manager, filename="Policy.pdf", content=_pdf("mgr"), roles=["all"])
    assert response.status_code == 403


def test_upload_unauthenticated(storage: FakeStorage):
    client = TestClient(app)
    response = _upload(client, filename="Policy.pdf", content=_pdf("anon"), roles=["all"])
    assert response.status_code == 401


def test_list_and_raw_hide_documents_outside_acl(admin_client: TestClient, storage: FakeStorage):
    title = "SecretHR.pdf"
    content = _pdf("hr-secret")
    uploaded = _upload(admin_client, filename=title, content=content, roles=["hr"])
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["id"]

    listed = admin_client.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0
    assert listed.json()["items"] == []

    status_resp = admin_client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_resp.status_code == 404
    assert status_resp.json()["detail"] == "Document not found"
    assert title not in status_resp.text

    raw = admin_client.get(f"/api/v1/documents/{doc_id}/raw")
    assert raw.status_code == 404
    assert raw.json()["detail"] == "Document not found"
    assert title not in raw.text
    assert raw.headers.get("content-type", "").startswith("application/json")

    hr_user = _register_user(UserRole.employee.value, departments=["hr"])
    visible = hr_user.get("/api/v1/documents")
    assert visible.status_code == 200
    items = visible.json()["items"]
    assert visible.json()["total"] == 1
    assert items[0]["id"] == doc_id
    assert items[0]["title"] == title

    raw_ok = hr_user.get(f"/api/v1/documents/{doc_id}/raw")
    assert raw_ok.status_code == 200
    assert raw_ok.headers["content-type"].startswith("application/pdf")
    assert raw_ok.content == content


def test_list_pagination_and_status_filter(admin_client: TestClient, storage: FakeStorage):
    ids = []
    for i in range(3):
        response = _upload(admin_client, filename=f"Doc{i}.pdf", content=_pdf(f"p{i}"), roles=["all"])
        assert response.status_code == 201
        ids.append(response.json()["id"])
    db = SessionLocal()
    db.get(Document, UUID(ids[0])).status = DocumentStatus.ready.value
    db.commit()
    db.close()

    page = admin_client.get("/api/v1/documents", params={"limit": 2, "offset": 0})
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2

    rest = admin_client.get("/api/v1/documents", params={"limit": 2, "offset": 2})
    assert rest.json()["total"] == 3
    assert len(rest.json()["items"]) == 1

    ready = admin_client.get("/api/v1/documents", params={"status": "ready"})
    assert ready.status_code == 200
    assert ready.json()["total"] == 1
    assert ready.json()["items"][0]["id"] == ids[0]


def test_status_returns_last_error_for_visible_doc(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("st"), roles=["admin"])
    doc_id = response.json()["id"]
    db = SessionLocal()
    doc = db.get(Document, UUID(doc_id))
    doc.status = DocumentStatus.failed.value
    doc.last_error = "parser boom"
    db.commit()
    db.close()

    status_resp = admin_client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["id"] == doc_id
    assert body["status"] == "failed"
    assert body["last_error"] == "parser boom"
    assert "title" not in body


def test_delete_cascades_postgres_and_minio(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("del"), roles=["hr"])
    assert response.status_code == 201
    doc_id = UUID(response.json()["id"])
    db = SessionLocal()
    db.add(
        DocumentChunk(
            document_id=doc_id,
            chunk_id=make_chunk_id(doc_id, 1, 0),
            page_number=1,
            access_roles=["hr"],
            content="secret",
        )
    )
    db.commit()
    path = db.get(Document, doc_id).file_path
    chunk_id = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).one().id
    db.close()
    assert path in storage.objects

    deleted = admin_client.delete(f"/api/v1/documents/{doc_id}")
    assert deleted.status_code == 204
    assert path not in storage.objects
    db = SessionLocal()
    assert db.get(Document, doc_id) is None
    assert db.get(DocumentChunk, chunk_id) is None
    db.close()


def test_delete_requires_admin(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("no-del"), roles=["all"])
    doc_id = response.json()["id"]
    employee = _register_user(UserRole.employee.value)
    assert employee.delete(f"/api/v1/documents/{doc_id}").status_code == 403
    db = SessionLocal()
    assert db.get(Document, UUID(doc_id)) is not None
    db.close()


def test_delete_missing_is_404(admin_client: TestClient, storage: FakeStorage):
    missing = uuid4()
    response = admin_client.delete(f"/api/v1/documents/{missing}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


def test_upload_json_access_roles_field(admin_client: TestClient, storage: FakeStorage):
    response = _upload(
        admin_client,
        filename="Policy.pdf",
        content=_pdf("json-roles"),
        roles='["all","engineering"]',
    )
    assert response.status_code == 201
    assert response.json()["access_roles"] == ["all", "engineering"]


def test_upload_rate_limit(admin_client: TestClient, storage: FakeStorage, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_PER_MINUTE", "1")
    get_settings.cache_clear()
    first = _upload(admin_client, filename="A.pdf", content=_pdf("rl1"), roles=["all"])
    assert first.status_code == 201
    second = _upload(admin_client, filename="B.pdf", content=_pdf("rl2"), roles=["all"])
    assert second.status_code == 429
    get_settings.cache_clear()
