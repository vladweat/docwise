"""FastAPI entry: middleware, `/api/v1` router, health, error handlers."""

from fastapi import FastAPI

from app.core.proxy import apply_internal_no_proxy

apply_internal_no_proxy()

from app.api.health import router as health_router
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.core.lifespan import lifespan
from app.core.logging import setup_logging
from app.core.middleware import CsrfMiddleware, TenantCORSMiddleware
from app.core.sentry import init_sentry

settings = get_settings()
setup_logging(settings.log_level)
init_sentry()

_DOCS_ENABLED = settings.environment != "production"

# App semver is independent of the URL prefix `/api/v1` (see `app.api.API_V1`).
app = FastAPI(
    title="Docwise API",
    version="0.1.0",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
    lifespan=lifespan,
)

register_error_handlers(app)
app.include_router(health_router)
app.include_router(api_router)
app.add_middleware(CsrfMiddleware)
app.add_middleware(
    TenantCORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
