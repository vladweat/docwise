"""Liveness (`/health`) and readiness (`/ready`) dependency checks."""

import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import check_pgvector, check_postgres
from app.services.billing import billing_readiness
from app.services.storage import get_object_storage
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)
settings = get_settings()
_DOCS_ENABLED = settings.environment != "production"

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    environment: str
    postgres: str
    redis: str
    pgvector: str
    minio: str
    billing: str


def _check_redis() -> bool:
    return bool(get_redis_client().ping())


def _check_minio() -> bool:
    response = httpx.get(
        f"{settings.s3_endpoint.rstrip('/')}/minio/health/live",
        timeout=5.0,
        trust_env=False,
    )
    if response.status_code != 200:
        return False
    return get_object_storage().bucket_is_ready()


@router.get("/")
def root() -> dict:
    return {"service": "docwise-backend", "docs": "/docs" if _DOCS_ENABLED else None}


@router.get("/health", response_model=LivenessResponse)
def health() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=None)
def ready() -> ReadyResponse | JSONResponse:
    runtime = get_settings()
    checks = {"postgres": "error", "redis": "error", "pgvector": "error", "minio": "error"}

    try:
        check_postgres()
        checks["postgres"] = "ok"
    except Exception as exc:
        logger.warning("Postgres check failed: %s", exc)

    try:
        if _check_redis():
            checks["redis"] = "ok"
    except Exception as exc:
        logger.warning("Redis check failed: %s", exc)

    try:
        if check_pgvector():
            checks["pgvector"] = "ok"
    except Exception as exc:
        logger.warning("pgvector check failed: %s", exc)

    try:
        if _check_minio():
            checks["minio"] = "ok"
    except Exception as exc:
        logger.warning("MinIO check failed: %s", exc)

    billing = billing_readiness()
    required_ok = all(value == "ok" for value in checks.values())
    billing_ok = billing in {"ok", "dev"}
    all_ok = required_ok and billing_ok
    payload = ReadyResponse(
        status="ok" if all_ok else "degraded",
        environment=runtime.environment,
        billing=billing,
        **checks,
    )
    if not all_ok:
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
