"""HTTP metrics use route templates and avoid recording the scrape itself."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from prometheus_client import generate_latest
from fastapi.testclient import TestClient

from app.core.metrics import (
    LLM_CACHE_OPERATIONS,
    LLM_REQUEST_FAILURES,
    RERANK_DURATION,
    RETRIEVAL_DURATION,
    HttpMetricsMiddleware,
    REGISTRY,
)


def test_request_metrics_use_route_template_not_raw_path():
    async def app(scope, _receive, send):
        scope["route"] = SimpleNamespace(path="/api/v1/chat/sessions/{session_id}")
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    middleware = HttpMetricsMiddleware(app)
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/chat/sessions/private-session-id",
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(middleware(scope, receive, send))

    output = generate_latest(REGISTRY).decode()
    assert 'route="/api/v1/chat/sessions/{session_id}"' in output
    assert 'status="200"' in output
    assert "private-session-id" not in output
    assert len(messages) == 2


def test_metrics_scrape_is_excluded_from_request_counters():
    called = False

    async def app(_scope, _receive, _send):
        nonlocal called
        called = True

    middleware = HttpMetricsMiddleware(app)
    scope = {"type": "http", "method": "GET", "path": "/metrics"}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(_message):
        return None

    asyncio.run(middleware(scope, receive, send))

    assert called
    assert 'route="/metrics"' not in generate_latest(REGISTRY).decode()


def test_metrics_endpoint_exposes_http_metrics_without_counting_its_scrape():
    from app.main import app

    LLM_CACHE_OPERATIONS.labels(outcome="miss").inc()
    LLM_REQUEST_FAILURES.labels(operation="stream").inc()
    RETRIEVAL_DURATION.observe(0.01)
    RERANK_DURATION.observe(0.01)
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "docwise_http_requests_total{method=\"GET\",route=\"/health\",status=\"200\"}" in response.text
    assert 'docwise_llm_cache_operations_total{outcome="miss"}' in response.text
    assert 'docwise_llm_request_failures_total{operation="stream"}' in response.text
    assert "docwise_retrieval_duration_seconds_count" in response.text
    assert "docwise_rerank_duration_seconds_count" in response.text
    assert 'route="/metrics"' not in response.text
