"""Naive UTC timestamps for DateTime columns that store UTC without tzinfo."""

from datetime import UTC, datetime


def utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
