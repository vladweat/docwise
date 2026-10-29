"""Search inspect stages, ENABLE_SEARCH_INSPECT, and audit without restricted chunk text."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import RagAuditLog
from app.models.document import Document, DocumentChunk, DocumentStatus, EMBEDDING_DIM, make_chunk_id
from app.models.user import UserRole
from app.services.retrieval.audit import chunk_ids_for_audit
from app.services.retrieval import (
    NO_CONTEXT_ANSWER,
    RetrievedChunk,
    RetrievalError,
    RetrievalResult,
    StageHit,
)
from helpers import api_error_message, register_payload, set_membership, wipe_app_tables

client = TestClient(app)

HR_TITLE = "ConfidentialCompPlan.pdf"
HR_TEXT = "Board-level severance is twenty-four monthly salaries."
PUBLIC_TITLE = "Canteen.pdf"
PUBLIC_TEXT = "The canteen menu is published weekly."


class HrKeywordReranker:
    def score(self, _query: str, documents: list[str]) -> list[float]:
        scores: list[float] = []
        for doc in documents:
            lowered = doc.lower()
            scores.append(0.99 if "severance" in lowered or "twenty-four" in lowered else 0.05)
        return scores


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


def _register(*, role: str = UserRole.admin.value, departments: list[str] | None = None) -> TestClient:
    http = TestClient(app)
    email = f"inspect-{uuid4().hex[:8]}@example.com"
    response = http.post("/api/v1/auth/register", json=register_payload(email))
    assert response.status_code == 201
    if role != UserRole.admin.value or departments:
        db = SessionLocal()
        set_membership(db, email, role=role, departments=departments or [])
        db.close()
    return http


def _org_id(http: TestClient) -> UUID:
    return UUID(http.get("/api/v1/auth/me").json()["organization_id"])


def _enable_inspect(monkeypatch, enabled: bool = True) -> None:
    monkeypatch.setenv("ENABLE_SEARCH_INSPECT", "true" if enabled else "false")
    get_settings.cache_clear()


def _seed_corpus(organization_id: UUID) -> tuple[UUID, UUID, list[float]]:
    db = SessionLocal()
    public = Document(
        organization_id=organization_id,
        title=PUBLIC_TITLE,
        file_path=f"{uuid4()}/{PUBLIC_TITLE}",
        file_hash=uuid4().hex,
        file_size_bytes=1024,
        access_roles=["all"],
        status=DocumentStatus.ready.value,
    )
    secret = Document(
        organization_id=organization_id,
        title=HR_TITLE,
        file_path=f"{uuid4()}/{HR_TITLE}",
        file_hash=uuid4().hex,
        file_size_bytes=2048,
        access_roles=["hr"],
        status=DocumentStatus.ready.value,
    )
    db.add_all([public, secret])
    db.flush()
    public_id = public.id
    secret_id = secret.id
    hr_vec = _vec(3)
    db.add_all(
        [
            DocumentChunk(
                document_id=public_id,
                organization_id=organization_id,
                chunk_id=make_chunk_id(public_id, 1, 0),
                page_number=1,
                access_roles=list(public.access_roles),
                content=PUBLIC_TEXT,
                token_count=len(PUBLIC_TEXT.split()),
                embedding=_vec(1),
                doc_title=public.title,
            ),
            DocumentChunk(
                document_id=secret_id,
                organization_id=organization_id,
                chunk_id=make_chunk_id(secret_id, 9, 0),
                page_number=9,
                access_roles=list(secret.access_roles),
                content=HR_TEXT,
                token_count=len(HR_TEXT.split()),
                embedding=hr_vec,
                doc_title=secret.title,
            ),
        ]
    )
    db.commit()
    db.close()
    return public_id, secret_id, hr_vec
    return public_id, secret_id, hr_vec


def _hit(*, title_page: int = 1, score: float = 0.5, snippet: str = PUBLIC_TEXT) -> StageHit:
    doc_id = uuid4()
    return StageHit(
        chunk_id=f"{doc_id}:{title_page}:0",
        document_id=doc_id,
        page=title_page,
        score=score,
        snippet=snippet,
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


def test_inspect_flag_defaults_off_in_production():
    production = Settings.model_construct(environment="production", enable_search_inspect=None)
    assert production.search_inspect_enabled is False
    development = Settings.model_construct(environment="development", enable_search_inspect=None)
    assert development.search_inspect_enabled is True
    forced = Settings.model_construct(environment="production", enable_search_inspect=True)
    assert forced.search_inspect_enabled is True
    disabled = Settings.model_construct(environment="development", enable_search_inspect=False)
    assert disabled.search_inspect_enabled is False


def test_audit_model_has_no_chunk_text_columns():
    columns = {column.name for column in RagAuditLog.__table__.columns}
    assert "content" not in columns
    assert "snippet" not in columns
    assert "embed_text" not in columns
    assert {
        "query",
        "user_id",
        "retrieved_chunk_ids",
        "latency_ms",
        "tokens_used",
        "feedback",
    } <= columns


def test_audit_chunk_ids_drop_non_uuid_text():
    good = uuid4()
    assert chunk_ids_for_audit([good, str(good), HR_TEXT, "not-a-uuid"]) == [str(good)]
    assert chunk_ids_for_audit([]) == []


def test_inspect_requires_auth():
    response = client.post("/api/v1/search/inspect", json={"query": "travel cap"})
    assert response.status_code == 401


def test_inspect_disabled_is_404_even_for_admin(monkeypatch):
    _enable_inspect(monkeypatch, enabled=False)
    http = _register(role=UserRole.admin.value)
    response = http.post("/api/v1/search/inspect", json={"query": "severance"})
    assert response.status_code == 404
    assert api_error_message(response) == "Not Found"
    assert HR_TITLE not in response.text
    assert HR_TEXT not in response.text


def test_inspect_employee_and_manager_forbidden(monkeypatch):
    _enable_inspect(monkeypatch)
    employee = _register(role=UserRole.employee.value)
    manager = _register(role=UserRole.manager.value)
    for http in (employee, manager):
        response = http.post("/api/v1/search/inspect", json={"query": "severance"})
        assert response.status_code == 403
        assert HR_TITLE not in response.text
        assert HR_TEXT not in response.text


def test_inspect_rejects_empty_query(monkeypatch):
    _enable_inspect(monkeypatch)
    http = _register()
    assert http.post("/api/v1/search/inspect", json={"query": "   "}).status_code == 422


def test_inspect_returns_pipeline_stages(monkeypatch):
    _enable_inspect(monkeypatch)
    dense = _hit(title_page=1, score=0.8, snippet=PUBLIC_TEXT)
    sparse = _hit(title_page=1, score=0.4, snippet=PUBLIC_TEXT)
    rrf = _hit(title_page=1, score=0.03, snippet=PUBLIC_TEXT)
    reranked = _hit(title_page=1, score=0.91, snippet=PUBLIC_TEXT)
    chunk = RetrievedChunk(
        id=uuid4(),
        document_id=reranked.document_id,
        chunk_id=reranked.chunk_id,
        doc_title=PUBLIC_TITLE,
        page_number=1,
        content=PUBLIC_TEXT,
        access_roles=("all",),
        score=0.91,
    )

    def fake_retrieve(_db, user, query, **_kwargs):
        assert user.role == UserRole.admin.value
        assert "hr" not in query
        return RetrievalResult(
            chunks=[chunk],
            dense=[dense],
            sparse=[sparse],
            rrf=[rrf],
            reranked=[reranked],
            allowed_roles=tuple(user.allowed_roles()),
        )

    monkeypatch.setattr("app.services.retrieval.inspect.retrieve", fake_retrieve)
    http = _register(role=UserRole.admin.value)
    response = http.post("/api/v1/search/inspect", json={"query": "canteen menu", "limit": 15})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"dense", "sparse", "rrf", "reranked"}
    assert body["dense"][0]["chunk_id"] == dense.chunk_id
    assert body["sparse"][0]["chunk_id"] == sparse.chunk_id
    assert body["rrf"][0]["chunk_id"] == rrf.chunk_id
    assert body["reranked"][0]["chunk_id"] == reranked.chunk_id
    for key in ("dense", "sparse", "rrf", "reranked"):
        hit = body[key][0]
        UUID(hit["document_id"])
        assert hit["page"] == 1
        assert "snippet" in hit
        assert "score" in hit
        assert HR_TITLE not in hit["snippet"]

    db = SessionLocal()
    log = db.query(RagAuditLog).one()
    assert log.query == "canteen menu"
    assert log.retrieved_chunk_ids == [str(chunk.id)]
    assert log.latency_ms is not None
    assert log.tokens_used is None
    assert log.feedback is None
    dumped = json.dumps(log.retrieved_chunk_ids)
    assert PUBLIC_TEXT not in dumped
    assert HR_TEXT not in dumped
    db.close()


def test_inspect_respects_limit(monkeypatch):
    _enable_inspect(monkeypatch)
    rows = [_hit(title_page=index, score=1.0 - index / 100) for index in range(1, 12)]

    def fake_retrieve(_db, user, _query, **_kwargs):
        return RetrievalResult(
            chunks=[],
            dense=rows,
            sparse=rows,
            rrf=rows[:15],
            reranked=rows[:4],
            allowed_roles=tuple(user.allowed_roles()),
        )

    monkeypatch.setattr("app.services.retrieval.inspect.retrieve", fake_retrieve)
    http = _register()
    response = http.post("/api/v1/search/inspect", json={"query": "limit me", "limit": 3})
    assert response.status_code == 200
    body = response.json()
    assert len(body["dense"]) == 3
    assert len(body["sparse"]) == 3
    assert len(body["rrf"]) == 3
    assert len(body["reranked"]) == 3


def test_inspect_and_chat_do_not_confirm_hidden_document(monkeypatch):
    _enable_inspect(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()

    admin = _register(role=UserRole.admin.value, departments=[])
    employee = _register(role=UserRole.employee.value, departments=[])
    _public_id, secret_id, hr_vec = _seed_corpus(_org_id(admin))

    def fake_embed(texts, embedder=None):
        _ = texts, embedder
        return [hr_vec]

    monkeypatch.setattr("app.services.retrieval.embed_texts", fake_embed)
    monkeypatch.setattr("app.services.retrieval._default_reranker", HrKeywordReranker)

    question = "board-level severance twenty-four monthly salaries"

    inspect_resp = admin.post(
        "/api/v1/search/inspect",
        json={
            "query": question,
            "limit": 15,
            "access_roles": ["hr", "admin"],
            "document_ids": [str(secret_id)],
        },
    )
    assert inspect_resp.status_code == 200
    inspect_body = inspect_resp.text
    assert HR_TITLE not in inspect_body
    assert HR_TEXT not in inspect_body
    assert str(secret_id) not in inspect_body
    payload = inspect_resp.json()
    for key in ("dense", "sparse", "rrf", "reranked"):
        assert all(hit["document_id"] != str(secret_id) for hit in payload[key])

    chat_resp = employee.post("/api/v1/chat/stream", json={"query": question})
    assert chat_resp.status_code == 200
    events = _parse_sse(chat_resp.text)
    assert events[0]["type"] == "citations"
    assert events[0]["citations"] == []
    tokens = "".join(
        item["content"] for item in events if isinstance(item, dict) and item.get("type") == "token"
    )
    assert tokens == NO_CONTEXT_ANSWER
    assert HR_TITLE not in chat_resp.text
    assert HR_TEXT not in chat_resp.text
    assert "hidden" not in chat_resp.text.lower()
    assert str(secret_id) not in chat_resp.text

    db = SessionLocal()
    logs = db.query(RagAuditLog).all()
    assert logs
    for log in logs:
        blob = json.dumps(
            {
                "query": log.query,
                "ids": log.retrieved_chunk_ids,
                "tokens_used": log.tokens_used,
            }
        )
        assert HR_TEXT not in blob
        assert PUBLIC_TEXT not in (log.retrieved_chunk_ids or [])
        for item in log.retrieved_chunk_ids or []:
            UUID(str(item))
    db.close()
    get_settings.cache_clear()


def test_inspect_hr_admin_sees_hr_chunk(monkeypatch):
    _enable_inspect(monkeypatch)
    admin = _register(role=UserRole.admin.value, departments=["hr"])
    _public_id, secret_id, hr_vec = _seed_corpus(_org_id(admin))
    monkeypatch.setattr("app.services.retrieval.embed_texts", lambda texts, embedder=None: [hr_vec])
    monkeypatch.setattr("app.services.retrieval._default_reranker", HrKeywordReranker)

    response = admin.post("/api/v1/search/inspect", json={"query": "severance salaries"})
    assert response.status_code == 200
    body = response.json()
    reranked_ids = {hit["document_id"] for hit in body["reranked"]}
    assert str(secret_id) in reranked_ids
    assert any(HR_TEXT[:20] in hit["snippet"] for hit in body["reranked"])
    assert any(hit["page"] == 9 for hit in body["reranked"])


def test_inspect_retrieval_error_does_not_leak_titles(monkeypatch):
    _enable_inspect(monkeypatch)

    def boom(*_args, **_kwargs):
        raise RetrievalError(f"embedding failed for {HR_TITLE}")

    monkeypatch.setattr("app.services.retrieval.inspect.retrieve", boom)
    http = _register()
    response = http.post("/api/v1/search/inspect", json={"query": "severance"})
    assert response.status_code == 503
    assert api_error_message(response) == "Service temporarily unavailable"
    assert HR_TITLE not in response.text
