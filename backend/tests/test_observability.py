"""Low-cardinality RAG and answer-cache instrumentation."""

from uuid import uuid4

from prometheus_client import generate_latest

from app.core.metrics import REGISTRY
from app.services.chat import prompt
from app.services.retrieval import RetrievalResult


def test_answer_cache_records_hit_and_miss_without_sensitive_dimensions(monkeypatch):
    question = "private synthetic question about payroll"
    organization_id = uuid4()
    before_hit = REGISTRY.get_sample_value(
        "docwise_llm_cache_operations_total", {"outcome": "hit"}
    ) or 0
    before_miss = REGISTRY.get_sample_value(
        "docwise_llm_cache_operations_total", {"outcome": "miss"}
    ) or 0

    monkeypatch.setattr(prompt, "redis_get", lambda _key: None)
    assert prompt.load_cached_answer(question, ["all"], organization_id=organization_id) is None

    monkeypatch.setattr(
        prompt,
        "redis_get",
        lambda _key: {"answer": "A cached synthetic answer.", "citations": [], "chunk_ids": []},
    )
    cached = prompt.load_cached_answer(question, ["all"], organization_id=organization_id)

    assert cached is not None and cached.cached is True
    assert (
        REGISTRY.get_sample_value("docwise_llm_cache_operations_total", {"outcome": "hit"})
        == before_hit + 1
    )
    assert (
        REGISTRY.get_sample_value("docwise_llm_cache_operations_total", {"outcome": "miss"})
        == before_miss + 1
    )
    output = generate_latest(REGISTRY).decode()
    assert question not in output
    assert str(organization_id) not in output


def test_retrieval_records_latency_without_recording_question(monkeypatch):
    import app.services.retrieval as retrieval

    question = "private synthetic retrieval question"
    expected = RetrievalResult(chunks=[], allowed_roles=("all",))
    before = REGISTRY.get_sample_value("docwise_retrieval_duration_seconds_count") or 0
    monkeypatch.setattr(retrieval, "allowed_roles_for", lambda _user: ["all"])
    monkeypatch.setattr(retrieval, "embed_query", lambda _query, **_kwargs: [0.0])
    monkeypatch.setattr(retrieval, "hybrid_search", lambda *_args: object())
    monkeypatch.setattr(retrieval, "finish_retrieval", lambda *_args, **_kwargs: expected)

    result = retrieval.retrieve(None, object(), question)

    assert result is expected
    after = REGISTRY.get_sample_value("docwise_retrieval_duration_seconds_count") or 0
    assert after == before + 1
    assert question not in generate_latest(REGISTRY).decode()
