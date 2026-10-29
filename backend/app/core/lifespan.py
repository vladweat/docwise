"""Startup: secret key guard and MinIO bucket setup."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import DEFAULT_SECRET_KEY, get_settings
from app.services.storage import ensure_documents_bucket

logger = logging.getLogger(__name__)
settings = get_settings()


def assert_secret_key() -> None:
    """Refuse production boot with the default `SECRET_KEY`."""
    if settings.secret_key != DEFAULT_SECRET_KEY:
        return
    if settings.environment == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    logger.warning("SECRET_KEY is the default; do not use this in production")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    assert_secret_key()
    ensure_documents_bucket()
    yield
