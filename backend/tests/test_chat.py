"""Chat SSE, sessions, feedback, and role-scoped LLM cache. No live LLM."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.main import app
from app.models.audit import RagAuditLog
from app.models.chat import ChatMessage, ChatSession
from app.models.user import UserRole
from app.services.chat import (
    CACHE_VERSION,
    PERSIST_FAILED,
    SYSTEM_PROMPT,
    ChatPersistError,
    cache_key,
    canonical_allowed_roles,
)
from helpers import register_payload, set_membership, wipe_app_tables
from app.services.chat.llm import LLMUsage
from app.services.retrieval import NO_CONTEXT_ANSWER, RetrievedChunk, RetrievalResult

client = TestClient(app)

HR_TEXT = "Severance is three monthly salaries."
PUBLIC_TEXT = "Daily travel reimbursement is capped at 150 USD."


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
    return f"chat-{uuid4().hex[:8]}@example.com"


def _register(*, role: str = UserRole.admin.value, departments: list[str] | None = None) -> TestClient:
    http = TestClient(app)
    email = _unique_email()
    response = http.post("/api/v1/auth/register", json=register_payload(email))
    assert response.status_code == 201
    if role != UserRole.admin.value or departments:
        db = SessionLocal()
        set_membership(db, email, role=role, departments=departments or [])
        db.close()
    return http


def _invite_into(
    admin: TestClient,
    *,
    role: str = UserRole.employee.value,
    departments: list[str] | None = None,
) -> TestClient:
    email = _unique_email()
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


def _chunk(*, title: str, page: int, content: str, roles: tuple[str, ...]) -> RetrievedChunk:
    doc_id = uuid4()
    return RetrievedChunk(
        id=uuid4(),
        document_id=doc_id,
        chunk_id=f"{doc_id}:{page}:0",
        doc_title=title,
        page_number=page,
        content=content,
        access_roles=roles,
        score=0.9,
    )


def _result(chunks: list[RetrievedChunk], user) -> RetrievalResult:
    return RetrievalResult(chunks=chunks, allowed_roles=tuple(user.allowed_roles()))


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


def _meta(events: list[dict | str]) -> dict:
    return next(item for item in events if isinstance(item, dict) and item.get("type") == "meta")


def _event_types(events: list[dict | str]) -> list[str]:
    return [item["type"] if isinstance(item, dict) else item for item in events]


def test_cache_key_includes_org_and_canonical_allowed_roles():
    org_a = uuid4()
    org_b = uuid4()
    employee = cache_key("travel cap", ["employee", "all"], organization_id=org_a)
    admin = cache_key("travel cap", ["admin", "all"], organization_id=org_a)
    shuffled = cache_key("travel cap", ["all", "employee"], organization_id=org_a)
    other_org = cache_key("travel cap", ["employee", "all"], organization_id=org_b)
    bumped = cache_key("travel cap", ["employee", "all"], organization_id=org_a, index_generation=1)
    assert employee != admin
    assert employee == shuffled
    assert employee != other_org
    assert employee != bumped
    assert employee.startswith(f"llm_cache:{CACHE_VERSION}:{org_a}:")
    assert canonical_allowed_roles(["hr", "all", "hr", "employee"]) == ("all", "employee", "hr")


def test_stream_requires_auth():
    response = client.post("/api/v1/chat/stream", json={"query": "travel cap?"})
    assert response.status_code == 401


def test_sessions_require_auth():
    assert client.get("/api/v1/chat/sessions").status_code == 401
    assert client.get(f"/api/v1/chat/sessions/{uuid4()}").status_code == 401
    assert client.delete(f"/api/v1/chat/sessions/{uuid4()}").status_code == 401
    assert client.post(
        "/api/v1/chat/feedback",
        json={"message_id": str(uuid4()), "rating": 1},
    ).status_code == 401


def test_stream_rejects_empty_query():
    http = _register()
    response = http.post("/api/v1/chat/stream", json={"query": "   "})
    assert response.status_code == 422


def test_stream_unknown_session_is_404():
    http = _register()
    response = http.post(
        "/api/v1/chat/stream",
        json={"query": "travel cap?", "session_id": str(uuid4())},
    )
    assert response.status_code == 404
    assert "not found" in response.json()["error"]["message"].lower()


def test_stream_sse_order_and_citation_shape(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))

    def fake_retrieve(_db, user, query, **_kwargs):
        assert "access_roles" not in query
        return _result([public], user)

    def fake_stream(messages, **_kwargs):
        joined = " ".join(item["content"] for item in messages)
        assert PUBLIC_TEXT in joined
        assert SYSTEM_PROMPT in joined
        yield "The cap is 150 USD "
        yield "[Travel.pdf, p. 4]."
        yield LLMUsage(tokens_used=24, cost_usd=Decimal("0.000002"))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    http = _register(role=UserRole.employee.value)
    question = f"What is the daily travel cap {uuid4().hex}?"
    response = http.post("/api/v1/chat/stream", json={"query": question})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    events = _parse_sse(response.text)
    types = _event_types(events)
    assert types[0] == "citations"
    assert "token" in types
    assert types[-2] == "meta"
    assert types[-1] == "[DONE]"
    assert types.index("citations") < types.index("token")

    citations = events[0]["citations"]
    assert citations[0]["doc_title"] == "Travel.pdf"
    assert citations[0]["page"] == 4
    UUID(citations[0]["doc_id"])
    assert "150 USD" in citations[0]["snippet"]
    assert "file.sol" not in json.dumps(citations)

    tokens = "".join(
        item["content"] for item in events if isinstance(item, dict) and item.get("type") == "token"
    )
    assert tokens == "The cap is 150 USD [Travel.pdf, p. 4]."
    meta = _meta(events)
    assert meta["cached"] is False
    assert meta["tokens_used"] == 24
    UUID(meta["session_id"])
    UUID(meta["message_id"])

    listed = http.get("/api/v1/chat/sessions")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == meta["session_id"]
    assert "travel cap" in (body["items"][0]["title"] or "").lower()

    detail = http.get(f"/api/v1/chat/sessions/{meta['session_id']}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert [item["role"] for item in messages] == ["user", "assistant"]
    assert messages[0]["content"] == question
    assert messages[1]["sources"][0]["page"] == 4
    get_settings.cache_clear()


def test_empty_retrieval_refuses_without_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    calls = {"stream": 0}

    def fake_retrieve(_db, user, _query, **_kwargs):
        return _result([], user)

    def fake_stream(_messages, **_kwargs):
        calls["stream"] += 1
        yield "should not run"
        yield LLMUsage()

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    http = _register(role=UserRole.employee.value)
    response = http.post("/api/v1/chat/stream", json={"query": f"unknown policy {uuid4().hex}"})
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events[0]["type"] == "citations"
    assert events[0]["citations"] == []
    tokens = "".join(
        item["content"] for item in events if isinstance(item, dict) and item.get("type") == "token"
    )
    assert tokens == NO_CONTEXT_ANSWER
    assert calls["stream"] == 0
    get_settings.cache_clear()


def test_openai_not_configured_when_chunks_exist(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))
    monkeypatch.setattr(
        "app.services.chat.retrieve",
        lambda db, user, query, **k: _result([public], user),
    )

    http = _register()
    response = http.post("/api/v1/chat/stream", json={"query": f"travel {uuid4().hex}"})
    assert response.status_code == 503
    db = SessionLocal()
    assert db.query(ChatSession).count() == 0
    db.close()
    get_settings.cache_clear()


def test_history_does_not_bypass_acl(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))
    captured: dict = {"retrieve_users": [], "prompts": []}

    def fake_retrieve(_db, user, query, **_kwargs):
        captured["retrieve_users"].append((user.role, tuple(user.allowed_roles()), query))
        return _result([public], user)

    def fake_stream(messages, **_kwargs):
        captured["prompts"].append(messages)
        yield "Follow-up from Travel.pdf, p. 4."
        yield LLMUsage(tokens_used=8, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    http = _register(role=UserRole.employee.value)
    first = http.post("/api/v1/chat/stream", json={"query": f"travel cap {uuid4().hex}"})
    assert first.status_code == 200
    session_id = _meta(_parse_sse(first.text))["session_id"]
    follow = f"what about contractors {uuid4().hex}?"
    second = http.post(
        "/api/v1/chat/stream",
        json={"query": follow, "session_id": session_id},
    )
    assert second.status_code == 200
    assert len(captured["retrieve_users"]) == 2
    assert all(roles == ("all", "employee") for _role, roles, _q in captured["retrieve_users"])
    second_prompt = captured["prompts"][1]
    prompt_text = json.dumps(second_prompt)
    assert follow in prompt_text
    assert PUBLIC_TEXT in prompt_text
    assert HR_TEXT not in prompt_text
    user_contents = [item["content"] for item in second_prompt if item["role"] == "user"]
    assert follow in user_contents
    get_settings.cache_clear()


def test_admin_cache_is_not_served_to_employee(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    question = f"What is the severance policy {uuid4().hex}?"
    hr = _chunk(title="HR.pdf", page=7, content=HR_TEXT, roles=("hr",))
    calls = {"stream": 0, "employee_retrieve": 0}

    def fake_retrieve(_db, user, _query, **_kwargs):
        if user.role == UserRole.admin.value:
            return _result([hr], user)
        calls["employee_retrieve"] += 1
        return _result([], user)

    def fake_stream(messages, **_kwargs):
        calls["stream"] += 1
        joined = " ".join(item["content"] for item in messages)
        assert HR_TEXT in joined
        yield "Severance is three monthly salaries [HR.pdf, p. 7]."
        yield LLMUsage(tokens_used=11, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    admin = _register(role=UserRole.admin.value)
    employee = _register(role=UserRole.employee.value, departments=[])

    admin_resp = admin.post("/api/v1/chat/stream", json={"query": question})
    assert admin_resp.status_code == 200
    admin_events = _parse_sse(admin_resp.text)
    admin_tokens = "".join(
        item["content"] for item in admin_events if isinstance(item, dict) and item.get("type") == "token"
    )
    assert "Severance" in admin_tokens
    assert admin_events[0]["citations"][0]["doc_title"] == "HR.pdf"

    employee_resp = employee.post("/api/v1/chat/stream", json={"query": question})
    assert employee_resp.status_code == 200
    employee_events = _parse_sse(employee_resp.text)
    assert employee_events[0]["type"] == "citations"
    assert employee_events[0]["citations"] == []
    employee_tokens = "".join(
        item["content"]
        for item in employee_events
        if isinstance(item, dict) and item.get("type") == "token"
    )
    assert employee_tokens == NO_CONTEXT_ANSWER
    assert "Severance" not in employee_tokens
    assert "HR.pdf" not in employee_resp.text
    assert calls["stream"] == 1
    assert calls["employee_retrieve"] == 1
    get_settings.cache_clear()


def test_same_roles_share_cache(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    question = f"canteen hours {uuid4().hex}"
    public = _chunk(title="Office.pdf", page=1, content="Canteen is open 12-15.", roles=("all",))
    calls = {"stream": 0, "retrieve": 0}

    def fake_retrieve(_db, user, _query, **_kwargs):
        calls["retrieve"] += 1
        return _result([public], user)

    def fake_stream(_messages, **_kwargs):
        calls["stream"] += 1
        yield "Canteen is open 12-15 [Office.pdf, p. 1]."
        yield LLMUsage(tokens_used=9, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    admin = _register()
    first = _invite_into(admin, role=UserRole.employee.value)
    second = _invite_into(admin, role=UserRole.employee.value)
    a = first.post("/api/v1/chat/stream", json={"query": question})
    b = second.post("/api/v1/chat/stream", json={"query": question})
    assert a.status_code == 200
    assert b.status_code == 200
    meta = _meta(_parse_sse(b.text))
    assert meta["cached"] is True
    assert meta["tokens_used"] is None
    assert calls["stream"] == 1
    assert calls["retrieve"] == 1
    db = SessionLocal()
    logs = db.query(RagAuditLog).order_by(RagAuditLog.created_at.asc()).all()
    assert logs[-1].tokens_used is None
    assert any(log.tokens_used == 9 for log in logs)
    db.close()
    get_settings.cache_clear()


def test_sessions_are_private(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.chat.retrieve",
        lambda db, user, query, **k: _result([], user),
    )
    owner = _register(role=UserRole.employee.value)
    other = _register(role=UserRole.employee.value)
    response = owner.post("/api/v1/chat/stream", json={"query": f"private {uuid4().hex}"})
    session_id = _meta(_parse_sse(response.text))["session_id"]
    assert other.get("/api/v1/chat/sessions").json()["total"] == 0
    hidden = other.get(f"/api/v1/chat/sessions/{session_id}")
    assert hidden.status_code == 404
    assert "not found" in hidden.json()["error"]["message"].lower()
    stolen = other.post(
        "/api/v1/chat/stream",
        json={"query": "follow up", "session_id": session_id},
    )
    assert stolen.status_code == 404
    assert other.delete(f"/api/v1/chat/sessions/{session_id}").status_code == 404
    removed = owner.delete(f"/api/v1/chat/sessions/{session_id}")
    assert removed.status_code == 204
    assert owner.get(f"/api/v1/chat/sessions/{session_id}").status_code == 404
    assert owner.get("/api/v1/chat/sessions").json()["total"] == 0
    get_settings.cache_clear()


def test_feedback_own_message_only(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.chat.retrieve",
        lambda db, user, query, **k: _result([], user),
    )
    owner = _register(role=UserRole.employee.value)
    other = _register(role=UserRole.employee.value)
    response = owner.post("/api/v1/chat/stream", json={"query": f"feedback {uuid4().hex}"})
    events = _parse_sse(response.text)
    meta = _meta(events)
    message_id = meta["message_id"]

    ok = owner.post("/api/v1/chat/feedback", json={"message_id": message_id, "rating": 1})
    assert ok.status_code == 204
    forbidden = other.post("/api/v1/chat/feedback", json={"message_id": message_id, "rating": -1})
    assert forbidden.status_code == 404

    db = SessionLocal()
    log = db.query(RagAuditLog).filter(RagAuditLog.message_id == UUID(message_id)).one()
    assert log.feedback == 1
    user_msg = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == UUID(meta["session_id"]), ChatMessage.role == "user")
        .one()
    )
    user_fb = owner.post("/api/v1/chat/feedback", json={"message_id": str(user_msg.id), "rating": -1})
    assert user_fb.status_code == 404
    db.close()
    get_settings.cache_clear()


def test_chat_rate_limit(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MINUTE", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.services.chat.retrieve",
        lambda db, user, query, **k: _result([], user),
    )
    http = _register(role=UserRole.employee.value)
    first = http.post("/api/v1/chat/stream", json={"query": f"rl-a {uuid4().hex}"})
    second = http.post("/api/v1/chat/stream", json={"query": f"rl-b {uuid4().hex}"})
    assert first.status_code == 200
    assert second.status_code == 429
    get_settings.cache_clear()


def test_client_roles_in_body_are_ignored(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))
    seen: list[tuple[str, tuple[str, ...]]] = []

    def fake_retrieve(_db, user, _query, **_kwargs):
        seen.append((user.role, tuple(user.allowed_roles())))
        return _result([public], user)

    def fake_stream(_messages, **_kwargs):
        yield "ok"
        yield LLMUsage(tokens_used=1, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    http = _register(role=UserRole.employee.value)
    response = http.post(
        "/api/v1/chat/stream",
        json={
            "query": f"ignore roles {uuid4().hex}",
            "access_roles": ["admin", "hr"],
            "document_ids": [str(uuid4())],
            "organization_id": str(uuid4()),
        },
    )
    assert response.status_code == 200
    assert seen == [("employee", ("all", "employee"))]
    get_settings.cache_clear()


def test_cache_miss_after_index_generation_bump(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    question = f"canteen hours {uuid4().hex}"
    public = _chunk(title="Office.pdf", page=1, content="Canteen is open 12-15.", roles=("all",))
    calls = {"stream": 0}

    def fake_retrieve(_db, user, _query, **_kwargs):
        return _result([public], user)

    def fake_stream(_messages, **_kwargs):
        calls["stream"] += 1
        yield "Canteen is open 12-15 [Office.pdf, p. 1]."
        yield LLMUsage(tokens_used=9, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    from app.services.chat.llm_cache import invalidate_llm_cache

    admin = _register()
    first = _invite_into(admin, role=UserRole.employee.value)
    second = _invite_into(admin, role=UserRole.employee.value)
    org_id = UUID(first.get("/api/v1/auth/me").json()["organization_id"])
    a = first.post("/api/v1/chat/stream", json={"query": question})
    assert a.status_code == 200
    assert _meta(_parse_sse(a.text))["cached"] is False

    db = SessionLocal()
    invalidate_llm_cache(db, org_id)
    db.commit()
    db.close()

    b = second.post("/api/v1/chat/stream", json={"query": question})
    assert b.status_code == 200
    assert _meta(_parse_sse(b.text))["cached"] is False
    assert calls["stream"] == 2
    get_settings.cache_clear()


def test_stream_releases_db_before_llm_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))
    from app.core.database import SessionLocal as RealSessionLocal

    class Counter:
        open_count = 0

    def factory():
        session = RealSessionLocal()
        Counter.open_count += 1
        original_close = session.close

        def close():
            Counter.open_count -= 1
            return original_close()

        session.close = close
        return session

    monkeypatch.setattr("app.services.chat.SessionLocal", factory)
    monkeypatch.setattr(
        "app.services.chat.retrieve",
        lambda db, user, query, **k: _result([public], user),
    )

    held = {"during_stream": None}

    def fake_stream(_messages, **_kwargs):
        held["during_stream"] = Counter.open_count
        yield "ok"
        yield LLMUsage(tokens_used=1, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)
    http = _register(role=UserRole.employee.value)
    response = http.post("/api/v1/chat/stream", json={"query": f"travel {uuid4().hex}"})
    assert response.status_code == 200
    assert held["during_stream"] == 0
    get_settings.cache_clear()


def test_split_path_releases_db_during_embed_and_rerank(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    from app.core.database import SessionLocal as RealSessionLocal
    from app.services.retrieval import HybridPool, RetrievalResult

    class Counter:
        open_count = 0

    def factory():
        session = RealSessionLocal()
        Counter.open_count += 1
        original_close = session.close

        def close():
            Counter.open_count -= 1
            return original_close()

        session.close = close
        return session

    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))
    held = {"embed": None, "hybrid": None, "rerank": None, "stream": None}

    def fake_embed(query, *, embedder=None):
        held["embed"] = Counter.open_count
        return [0.0] * 384

    def fake_hybrid(_db, _user, _query, _vector):
        held["hybrid"] = Counter.open_count
        return HybridPool(allowed_roles=("all", "employee"))

    def fake_finish(_query, _pool, *, reranker=None):
        held["rerank"] = Counter.open_count
        return RetrievalResult(chunks=[public], allowed_roles=("all", "employee"))

    def fake_stream(_messages, **_kwargs):
        held["stream"] = Counter.open_count
        yield "ok"
        yield LLMUsage(tokens_used=2, cost_usd=Decimal("0.000001"))

    monkeypatch.setattr("app.services.chat.SessionLocal", factory)
    monkeypatch.setattr("app.services.chat.embed_query", fake_embed)
    monkeypatch.setattr("app.services.chat.hybrid_search", fake_hybrid)
    monkeypatch.setattr("app.services.chat.finish_retrieval", fake_finish)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)

    http = _register(role=UserRole.employee.value)
    response = http.post("/api/v1/chat/stream", json={"query": f"split {uuid4().hex}"})
    assert response.status_code == 200
    assert held["embed"] == 0
    assert held["hybrid"] == 1
    assert held["rerank"] == 0
    assert held["stream"] == 0
    get_settings.cache_clear()


def test_persist_failure_emits_error_after_tokens(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    public = _chunk(title="Travel.pdf", page=4, content=PUBLIC_TEXT, roles=("all",))

    def fake_retrieve(_db, user, query, **_kwargs):
        return _result([public], user)

    def fake_stream(_messages, **_kwargs):
        yield "The cap is 150 USD."
        yield LLMUsage(tokens_used=4, cost_usd=Decimal("0.000001"))

    def boom(*_args, **_kwargs):
        raise ChatPersistError(PERSIST_FAILED)

    monkeypatch.setattr("app.services.chat.retrieve", fake_retrieve)
    monkeypatch.setattr("app.services.chat.stream_openai", fake_stream)
    monkeypatch.setattr("app.services.chat._persist_turn", boom)

    http = _register(role=UserRole.employee.value)
    response = http.post("/api/v1/chat/stream", json={"query": f"travel {uuid4().hex}"})
    assert response.status_code == 200
    events = _parse_sse(response.text)
    types = _event_types(events)
    assert types[0] == "citations"
    assert "token" in types
    tokens = "".join(
        item["content"] for item in events if isinstance(item, dict) and item.get("type") == "token"
    )
    assert "150 USD" in tokens
    meta = _meta(events)
    assert meta["session_id"] is None
    assert meta["message_id"] is None
    errors = [item for item in events if isinstance(item, dict) and item.get("type") == "error"]
    assert errors
    assert errors[0]["content"] == PERSIST_FAILED
    db = SessionLocal()
    assert db.query(ChatSession).count() == 0
    db.close()
    listed = http.get("/api/v1/chat/sessions")
    assert listed.json()["total"] == 0
    get_settings.cache_clear()

