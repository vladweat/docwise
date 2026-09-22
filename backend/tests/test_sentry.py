"""Sentry scrubbing before send."""

from app.core.sentry import before_send, capture_pipeline_error, init_sentry


def test_before_send_strips_request_body_and_document_text():
    leak = "Travel reimbursement policy page 12. " + ("Employees may claim $150 per day. " * 40)
    event = {
        "request": {
            "data": {"content": leak},
            "headers": {"Authorization": "Bearer secret", "content-type": "application/json"},
        },
        "extra": {"note": leak},
        "exception": {
            "values": [
                {"value": leak},
            ]
        },
    }
    cleaned = before_send(event, None)
    assert "data" not in cleaned["request"]
    assert cleaned["request"]["headers"]["Authorization"] == "[redacted]"
    assert cleaned["extra"]["note"] == "[redacted]"
    assert cleaned["exception"]["values"][0]["value"] == "[redacted]"


def test_init_sentry_noop_without_dsn(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SENTRY_DSN", "")
    get_settings.cache_clear()
    init_sentry()
    capture_pipeline_error("llm", RuntimeError("boom"))
    get_settings.cache_clear()
