"""Tenant-aware CORS and CSRF middleware for cookie auth."""

from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.csrf import enforce_csrf
from app.core.errors import api_error_response
from app.services.org.domains import origin_allowed


class TenantCORSMiddleware(CORSMiddleware):
    """Allow configured SPA origins plus verified/platform hostnames (not the request body)."""

    def is_allowed_origin(self, origin: str) -> bool:
        if super().is_allowed_origin(origin):
            return True
        return origin_allowed(origin)


class CsrfMiddleware(BaseHTTPMiddleware):
    """Run CSRF checks before `/api/v1` mutating handlers."""

    async def dispatch(self, request: Request, call_next):
        try:
            enforce_csrf(request)
        except HTTPException as exc:
            return api_error_response(
                exc.status_code,
                "security.csrf_failed",
                "CSRF check failed",
            )
        return await call_next(request)
