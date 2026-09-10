import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app.api.auth import router as auth_router
from app.api.billing import router as billing_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.organizations import router as organizations_router
from app.api.search import router as search_router
from app.core.config import DEFAULT_SECRET_KEY, get_settings
from app.core.csrf import enforce_csrf
from app.core.database import check_pgvector, check_postgres
from app.core.sentry import init_sentry
from app.services.storage import ensure_documents_bucket, get_object_storage
from app.utils.logging import setup_logging
from app.utils.redis_lock import get_redis_client

settings = get_settings()
setup_logging(settings.log_level)
init_sentry()
logger = logging.getLogger(__name__)

_DOCS_ENABLED = settings.environment != "production"


def _run_migrations() -> None:
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")


def _assert_secret_key() -> None:
    if settings.secret_key != DEFAULT_SECRET_KEY:
        return
    if settings.environment == "production":
        raise RuntimeError("SECRET_KEY must be set in production")
    logger.warning("SECRET_KEY is the default; do not use this in production")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _assert_secret_key()
    try:
        _run_migrations()
        logger.info("Database migrations applied")
    except Exception as exc:
        logger.error("Migration failed: %s", exc)
        raise
    ensure_documents_bucket()
    yield


class CsrfMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            enforce_csrf(request)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)


app = FastAPI(
    title="Docwise API",
    version="0.1.0",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(billing_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")

app.add_middleware(CsrfMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LivenessResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    environment: str
    postgres: str
    redis: str
    pgvector: str
    minio: str


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


@app.get("/")
def root() -> dict:
    return {"service": "docwise-backend", "docs": "/docs" if _DOCS_ENABLED else None}


@app.get("/health", response_model=LivenessResponse)
def health() -> LivenessResponse:
    return LivenessResponse(status="ok")


@app.get("/ready", response_model=None)
def ready() -> ReadyResponse | JSONResponse:
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

    all_ok = all(v == "ok" for v in checks.values())
    payload = ReadyResponse(
        status="ok" if all_ok else "degraded",
        environment=settings.environment,
        **checks,
    )
    if not all_ok:
        return JSONResponse(status_code=503, content=payload.model_dump())
    return payload
