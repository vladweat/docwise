"""Documents API: upload, ACL, delete, raw download."""

from __future__ import annotations

import hashlib
import uuid
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.documents import get_storage
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import BadRequestError
from app.main import app
from app.models.document import Document, DocumentChunk, DocumentStatus, make_chunk_id
from app.models.organization import Organization
from app.models.storage_deletion import StorageDeletion
from app.models.user import UserRole
from app.services.documents import parse_access_roles
from app.services.storage import StorageError
from helpers import api_error_message, register_payload, set_membership, wipe_app_tables
from pdf_fixtures import tagged_pdf_bytes


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


def _pdf(tag: str, pages: int = 1) -> bytes:
    return tagged_pdf_bytes(tag, pages=pages)


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
    monkeypatch.setattr("app.services.documents.upload.enqueue_ingestion", lambda document_id: None)


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
def admin_client() -> TestClient:
    client = TestClient(app)
    email = _unique_email()
    response = client.post(
        "/api/v1/auth/register",
        json=register_payload(email, organization_name="Docs Admin"),
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    return client


def _register_user(
    role: str,
    departments: list[str] | None = None,
    *,
    admin_client: TestClient | None = None,
) -> TestClient:
    client = TestClient(app)
    email = _unique_email()
    if admin_client is not None:
        invited = admin_client.post(
            "/api/v1/organizations/invites",
            json={"email": email, "role": role, "departments": departments or []},
        )
        assert invited.status_code == 201
        body = invited.json()
        assert body["status"] == "invited"
        response = client.post(
            "/api/v1/auth/register",
            json=register_payload(email, invite_token=body["invite_token"]),
        )
        assert response.status_code == 201
        return client

    response = client.post(
        "/api/v1/auth/register",
        json=register_payload(email),
    )
    assert response.status_code == 201
    db = SessionLocal()
    set_membership(db, email, role=role, departments=departments or [])
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
    assert parse_access_roles('["HR", "finance"]') == ["hr", "finance"]
    assert parse_access_roles(["finance", "finance"]) == ["finance"]
    assert parse_access_roles("hr, finance") == ["hr", "finance"]
    assert parse_access_roles(["all"]) == ["all"]
    with pytest.raises(BadRequestError):
        parse_access_roles(["all", "hr"])
    with pytest.raises(BadRequestError) as exc:
        parse_access_roles([])
    assert exc.value.status_code == 400


def test_upload_returns_201_pending_and_enqueues(admin_client: TestClient, storage: FakeStorage, monkeypatch):
    enqueued: list[UUID] = []
    monkeypatch.setattr(
        "app.services.documents.upload.enqueue_ingestion",
        lambda document_id: enqueued.append(document_id),
    )
    content = _pdf("upload-ok")
    response = _upload(admin_client, filename="Policy.pdf", content=content, roles=["admin", "hr"])
    assert response.status_code == 201
    body = response.json()
    UUID(body["id"])
    assert body["title"] == "Policy.pdf"
    assert body["status"] == "pending"
    assert body["access_roles"] == ["admin", "hr"]
    assert body["file_size_bytes"] == len(content)
    assert body["total_pages"] == 1
    assert enqueued == [UUID(body["id"])]
    assert any("/Policy.pdf" in key and key.startswith("orgs/") for key in storage.objects)
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
    detail = api_error_message(second)
    assert detail == "Document with this file hash already exists"
    assert existing_id not in detail
    assert "One.pdf" not in second.text
    db = SessionLocal()
    assert db.query(Document).count() == 1
    db.close()


def test_upload_rejects_non_pdf_and_oversize(admin_client: TestClient, storage: FakeStorage, monkeypatch):
    txt = _upload(admin_client, filename="notes.txt", content=_pdf("txt"), roles=["all"])
    assert txt.status_code == 400
    bad_magic = _upload(admin_client, filename="fake.pdf", content=b"not a pdf", roles=["all"])
    assert bad_magic.status_code == 400
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "20")
    get_settings.cache_clear()
    huge = _upload(admin_client, filename="big.pdf", content=_pdf("huge") + b"x" * 50, roles=["all"])
    assert huge.status_code == 413
    get_settings.cache_clear()
    assert storage.objects == {}


def test_upload_requires_admin_or_manager(storage: FakeStorage):
    employee = _register_user(UserRole.employee.value)
    response = _upload(employee, filename="Policy.pdf", content=_pdf("emp"), roles=["all"])
    assert response.status_code == 403

    manager = _register_user(UserRole.manager.value)
    response = _upload(manager, filename="Policy.pdf", content=_pdf("mgr"), roles=["all"])
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    assert response.json()["total_pages"] == 1


def test_access_options_are_dynamic_and_scoped_to_the_current_organization(admin_client: TestClient):
    _register_user("employee", ["hr", "legal"], admin_client=admin_client)

    other_admin = TestClient(app)
    other_admin.post(
        "/api/v1/auth/register",
        json=register_payload(_unique_email(), organization_name="Other Docs Org"),
    )
    _register_user("employee", ["sales"], admin_client=other_admin)

    own_options = admin_client.get("/api/v1/documents/access-options")
    other_options = other_admin.get("/api/v1/documents/access-options")

    assert own_options.status_code == 200
    assert own_options.json() == {
        "roles": ["admin", "employee", "manager"],
        "departments": ["hr", "legal"],
    }
    assert other_options.status_code == 200
    assert other_options.json()["departments"] == ["sales"]


def test_access_options_requires_admin_or_manager(admin_client: TestClient):
    manager = _register_user(UserRole.manager.value, admin_client=admin_client)
    employee = _register_user(UserRole.employee.value, admin_client=admin_client)

    assert manager.get("/api/v1/documents/access-options").status_code == 200
    assert employee.get("/api/v1/documents/access-options").status_code == 403


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
    assert api_error_message(status_resp) == "Document not found"
    assert title not in status_resp.text

    raw = admin_client.get(f"/api/v1/documents/{doc_id}/raw")
    assert raw.status_code == 404
    assert api_error_message(raw) == "Document not found"
    assert title not in raw.text
    assert raw.headers.get("content-type", "").startswith("application/json")

    hr_user = _register_user(UserRole.employee.value, departments=["hr"], admin_client=admin_client)
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

    employee = _register_user(UserRole.employee.value, admin_client=admin_client)
    hidden = employee.get("/api/v1/documents")
    assert hidden.status_code == 200
    assert hidden.json()["items"] == []
    assert title not in hidden.text
    raw_denied = employee.get(f"/api/v1/documents/{doc_id}/raw")
    assert raw_denied.status_code == 404
    assert api_error_message(raw_denied) == "Document not found"
    assert title not in raw_denied.text


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


def test_list_documents_includes_preview_snippet(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Preview.pdf", content=_pdf("preview"), roles=["all"])
    assert response.status_code == 201
    doc_id = response.json()["id"]
    db = SessionLocal()
    doc = db.get(Document, UUID(doc_id))
    assert doc is not None
    db.add(
        DocumentChunk(
            document_id=doc_id,
            organization_id=doc.organization_id,
            chunk_id=make_chunk_id(doc_id, 1, 0),
            page_number=1,
            access_roles=["all"],
            content="Preview content from the first page of the PDF.",
        )
    )
    doc.status = DocumentStatus.ready.value
    db.commit()
    db.close()

    listed = admin_client.get("/api/v1/documents")
    assert listed.status_code == 200
    body = listed.json()
    item = next(row for row in body["items"] if row["id"] == doc_id)
    assert isinstance(item["preview_snippet"], str)
    assert item["preview_snippet"]
    assert len(item["preview_snippet"]) <= 260


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
    assert body["stage"] is None
    assert "title" not in body
    assert "ingestion_stage" not in body


def test_status_returns_ingestion_stage(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("stage"), roles=["admin"])
    doc_id = response.json()["id"]
    db = SessionLocal()
    doc = db.get(Document, UUID(doc_id))
    doc.status = DocumentStatus.processing.value
    doc.ingestion_stage = "chunk"
    db.commit()
    db.close()

    status_resp = admin_client.get(f"/api/v1/documents/{doc_id}/status")
    assert status_resp.status_code == 200
    body = status_resp.json()
    assert body["status"] == "processing"
    assert body["stage"] == "chunk"
    assert body["last_error"] is None


def test_list_includes_last_error_for_failed_visible_doc(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("list-err"), roles=["admin"])
    doc_id = response.json()["id"]
    db = SessionLocal()
    doc = db.get(Document, UUID(doc_id))
    doc.status = DocumentStatus.failed.value
    doc.last_error = "parser boom"
    db.commit()
    db.close()

    listed = admin_client.get("/api/v1/documents")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == doc_id
    assert items[0]["status"] == "failed"
    assert items[0]["last_error"] == "parser boom"


def test_delete_cascades_postgres_and_queues_storage_cleanup(
    admin_client: TestClient,
    storage: FakeStorage,
    monkeypatch: pytest.MonkeyPatch,
):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("del"), roles=["hr"])
    assert response.status_code == 201
    doc_id = UUID(response.json()["id"])
    db = SessionLocal()
    stored = db.get(Document, doc_id)
    assert stored is not None
    db.add(
        DocumentChunk(
            document_id=doc_id,
            organization_id=stored.organization_id,
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
    db = SessionLocal()
    assert db.get(Document, doc_id) is None
    assert db.get(DocumentChunk, chunk_id) is None
    cleanup = db.query(StorageDeletion).filter(StorageDeletion.object_key == path).one()
    cleanup_id = cleanup.id
    assert path in storage.objects

    monkeypatch.setattr(
        "app.services.storage_deletions.get_object_storage",
        lambda: storage,
    )
    from app.services.storage_deletions import process_storage_deletions

    result = process_storage_deletions(db)
    assert result["deleted"] >= 1
    assert result["failed"] == 0
    assert result["remaining"] == 0
    assert db.get(StorageDeletion, cleanup_id) is None
    assert path not in storage.objects
    db.close()


def test_delete_requires_kb_admin(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("no-del"), roles=["all"])
    doc_id = response.json()["id"]
    employee = _register_user(UserRole.employee.value, admin_client=admin_client)
    assert employee.delete(f"/api/v1/documents/{doc_id}").status_code == 403
    db = SessionLocal()
    assert db.get(Document, UUID(doc_id)) is not None
    db.close()
    manager = _register_user(UserRole.manager.value, admin_client=admin_client)
    assert manager.delete(f"/api/v1/documents/{doc_id}").status_code == 204
    db = SessionLocal()
    assert db.get(Document, UUID(doc_id)) is None
    db.close()


def test_delete_keeps_list_consistent_if_minio_fails(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("orphan-obj"), roles=["all"])
    assert response.status_code == 201
    doc_id = UUID(response.json()["id"])

    def boom(key: str) -> None:
        raise StorageError("minio down")

    storage.delete_object = boom  # type: ignore[method-assign]
    deleted = admin_client.delete(f"/api/v1/documents/{doc_id}")
    assert deleted.status_code == 204
    db = SessionLocal()
    assert db.get(Document, doc_id) is None
    db.close()


def test_delete_missing_is_404(admin_client: TestClient, storage: FakeStorage):
    missing = uuid4()
    response = admin_client.delete(f"/api/v1/documents/{missing}")
    assert response.status_code == 404
    assert api_error_message(response) == "Document not found"


def test_upload_json_access_roles_field(admin_client: TestClient, storage: FakeStorage):
    response = _upload(
        admin_client,
        filename="Policy.pdf",
        content=_pdf("json-roles"),
        roles='["admin","engineering"]',
    )
    assert response.status_code == 201
    assert response.json()["access_roles"] == ["admin", "engineering"]


def test_upload_rate_limit(admin_client: TestClient, storage: FakeStorage, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOAD_PER_MINUTE", "1")
    get_settings.cache_clear()
    first = _upload(admin_client, filename="A.pdf", content=_pdf("rl1"), roles=["all"])
    assert first.status_code == 201
    second = _upload(admin_client, filename="B.pdf", content=_pdf("rl2"), roles=["all"])
    assert second.status_code == 429
    get_settings.cache_clear()


def test_patch_acl_updates_document_and_chunks(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("acl"), roles=["hr"])
    assert response.status_code == 201
    doc_id = UUID(response.json()["id"])
    db = SessionLocal()
    stored = db.get(Document, doc_id)
    assert stored is not None
    db.add(
        DocumentChunk(
            document_id=doc_id,
            organization_id=stored.organization_id,
            chunk_id=make_chunk_id(doc_id, 1, 0),
            page_number=1,
            access_roles=["hr"],
            content="secret",
            embedding=[0.1] * 384,
        )
    )
    db.add(
        DocumentChunk(
            document_id=doc_id,
            organization_id=stored.organization_id,
            chunk_id=make_chunk_id(doc_id, 2, 0),
            page_number=2,
            access_roles=["hr"],
            content="also secret",
            embedding=[0.2] * 384,
        )
    )
    db.commit()
    db.close()

    patched = admin_client.patch(
        f"/api/v1/documents/{doc_id}",
        json={"access_roles": ["engineering", "admin"]},
    )
    assert patched.status_code == 200
    assert patched.json()["access_roles"] == ["engineering", "admin"]
    assert patched.json()["id"] == str(doc_id)

    db = SessionLocal()
    stored = db.get(Document, doc_id)
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc_id).all()
    assert stored is not None
    assert stored.access_roles == ["engineering", "admin"]
    assert len(chunks) == 2
    assert all(chunk.access_roles == ["engineering", "admin"] for chunk in chunks)
    assert {chunk.content for chunk in chunks} == {"secret", "also secret"}
    assert all(chunk.embedding is not None for chunk in chunks)
    org = db.get(Organization, stored.organization_id)
    assert org is not None
    assert org.llm_index_generation >= 1
    db.close()

    hr = _register_user(UserRole.employee.value, departments=["hr"], admin_client=admin_client)
    listed = hr.get("/api/v1/documents")
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

    eng = _register_user(UserRole.employee.value, departments=["engineering"], admin_client=admin_client)
    visible = eng.get("/api/v1/documents")
    assert visible.status_code == 200
    assert visible.json()["total"] == 1
    assert visible.json()["items"][0]["id"] == str(doc_id)


def test_patch_acl_requires_admin(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("no-acl"), roles=["all"])
    doc_id = response.json()["id"]
    employee = _register_user(UserRole.employee.value, admin_client=admin_client)
    denied = employee.patch(f"/api/v1/documents/{doc_id}", json={"access_roles": ["hr"]})
    assert denied.status_code == 403
    db = SessionLocal()
    stored = db.get(Document, UUID(doc_id))
    assert stored is not None
    assert stored.access_roles == ["all"]
    db.close()


def test_patch_acl_missing_is_404(admin_client: TestClient):
    missing = uuid4()
    response = admin_client.patch(
        f"/api/v1/documents/{missing}",
        json={"access_roles": ["hr"]},
    )
    assert response.status_code == 404
    assert api_error_message(response) == "Document not found"


def test_patch_acl_rejects_empty_roles(admin_client: TestClient, storage: FakeStorage):
    response = _upload(admin_client, filename="Policy.pdf", content=_pdf("empty-acl"), roles=["hr"])
    doc_id = response.json()["id"]
    empty = admin_client.patch(f"/api/v1/documents/{doc_id}", json={"access_roles": []})
    assert empty.status_code == 422
