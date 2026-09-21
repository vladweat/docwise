"""Non-streaming LLM helper used by eval judges. No live network."""

from app.core.config import get_settings
from app.services.chat.llm import LLMUsage, OpenAIRequestError, complete_openai


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text or ""

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.closed = False
        self.last_payload = None

    def post(self, _url, headers=None, json=None):
        self.last_payload = json
        return self.response

    def close(self):
        self.closed = True


def test_complete_openai_returns_text_and_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    client = _FakeClient(
        _FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )
    )
    text, usage = complete_openai([{"role": "user", "content": "q"}], client=client)
    assert text == "hello"
    assert isinstance(usage, LLMUsage)
    assert usage.tokens_used == 3
    assert client.last_payload["stream"] is False
    assert client.closed is False


def test_complete_openai_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    client = _FakeClient(_FakeResponse(500, text="nope"))
    try:
        complete_openai([{"role": "user", "content": "q"}], client=client)
        raise AssertionError("expected OpenAIRequestError")
    except OpenAIRequestError as exc:
        assert "500" in str(exc)
    assert client.closed is False
