"""JSON logs with redaction. Infra, not a domain service."""

import logging

from pythonjsonlogger import jsonlogger

SENSITIVE_KEYS = {
    "source_code",
    "llm_answer",
    "answer",
    "question",
    "prompt",
    "messages",
    "files",
    "content",
    "chunk_text",
    "snippet",
    "authorization",
    "cookie",
    "password",
    "id_token",
    "access_token",
    "refresh_token",
}

LONG_MESSAGE_CHARS = 400


class RedactingJsonFormatter(jsonlogger.JsonFormatter):
    """JSON logs without document plaintext, secrets, or LLM completions."""

    def add_fields(self, log_record, record, message_dict) -> None:
        super().add_fields(log_record, record, message_dict)
        for key in list(log_record):
            if key.lower() in SENSITIVE_KEYS:
                log_record[key] = "[redacted]"
            elif key.lower() in {"exc_info", "exc_text", "stack_info"}:
                log_record[key] = "[redacted]"
        if record.exc_info and record.exc_info[0] is not None:
            log_record["exception_type"] = record.exc_info[0].__name__
        message = log_record.get("message")
        if isinstance(message, str) and len(message) >= LONG_MESSAGE_CHARS:
            log_record["message"] = "[redacted]"


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            handler.setFormatter(
                RedactingJsonFormatter(
                    "%(asctime)s %(name)s %(levelname)s %(message)s",
                    rename_fields={"asctime": "timestamp", "levelname": "level"},
                )
            )
        root.setLevel(level.upper())
        return

    handler = logging.StreamHandler()
    formatter = RedactingJsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(level.upper())
