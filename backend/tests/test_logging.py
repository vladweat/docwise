"""JSON log redaction of sensitive fields."""

import io
import json
import logging

from app.core.logging import RedactingJsonFormatter, setup_logging


def _format(record: logging.LogRecord) -> dict:
    formatter = RedactingJsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    return json.loads(formatter.format(record))


def test_redacts_document_text_extra():
    record = logging.LogRecord(
        "test",
        logging.INFO,
        __file__,
        1,
        "indexing done",
        (),
        None,
    )
    record.chunk_text = "Employees are eligible for up to $150/day travel reimbursement."
    record.content = "Confidential NDA clause 4.2"
    data = _format(record)
    assert data["chunk_text"] == "[redacted]"
    assert data["content"] == "[redacted]"


def test_redacts_llm_answer_extra():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "cached", (), None)
    record.llm_answer = "The daily cap is $150"
    record.answer = "The daily cap is $150"
    data = _format(record)
    assert data["llm_answer"] == "[redacted]"
    assert data["answer"] == "[redacted]"


def test_redacts_long_policy_message():
    source = "Travel reimbursement policy 4.2\n" + ("Employees may claim up to $150 per day.\n" * 20)
    record = logging.LogRecord("test", logging.INFO, __file__, 1, source, (), None)
    data = _format(record)
    assert data["message"] == "[redacted]"


def test_setup_logging_replaces_formatter():
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    setup_logging("INFO")
    setup_logging("DEBUG")
    assert root.handlers
    assert isinstance(root.handlers[0].formatter, RedactingJsonFormatter)


def test_short_messages_stay_plaintext():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "ok", (), None)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        RedactingJsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    )
    handler.emit(record)
    assert '"message": "ok"' in stream.getvalue()


def test_redacts_exception_message_and_traceback_but_keeps_exception_type():
    try:
        raise RuntimeError("private document text must never be logged")
    except RuntimeError:
        record = logging.LogRecord(
            "test",
            logging.ERROR,
            __file__,
            1,
            "request failed",
            (),
            __import__("sys").exc_info(),
        )

    data = _format(record)
    rendered = json.dumps(data)
    assert "private document text" not in rendered
    assert data["exception_type"] == "RuntimeError"
    assert data.get("exc_info") == "[redacted]"


def test_sentry_scrubs_short_exception_and_breadcrumb_messages():
    from app.core.sentry import before_send

    event = {
        "exception": {"values": [{"type": "RuntimeError", "value": "private query text"}]},
        "breadcrumbs": {"values": [{"message": "private answer text"}]},
    }

    scrubbed = before_send(event)
    assert scrubbed["exception"]["values"][0]["type"] == "RuntimeError"
    assert scrubbed["exception"]["values"][0]["value"] == "[redacted]"
    assert scrubbed["breadcrumbs"]["values"][0]["message"] == "[redacted]"
