from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException, Request, status

from app.api import API_V1
from app.core.config import get_settings
from app.services.org.domains import origin_allowed

CSRF_HEADER_VALUE = "Docwise"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_EXEMPT_PATHS = {f"{API_V1}/billing/webhooks/stripe"}


def _csrf_exempt(path: str) -> bool:
    if path in CSRF_EXEMPT_PATHS:
        return True
    return path.startswith(f"{API_V1}/auth/sso/") and path.endswith("/acs")


def request_origin(request: Request) -> str | None:
    origin = (request.headers.get("origin") or "").strip()
    if origin:
        return origin
    referer = (request.headers.get("referer") or "").strip()
    if not referer:
        return None
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def enforce_csrf(request: Request) -> None:
    """Require Origin allowlist or X-Requested-With when cookies are cross-site (SameSite=None)."""
    if request.method in SAFE_METHODS:
        return
    if _csrf_exempt(request.url.path):
        return
    if not request.url.path.startswith(API_V1):
        return

    settings = get_settings()
    samesite = (settings.cookie_samesite or "lax").strip().lower()
    if samesite in {"lax", "strict"}:
        return

    header = (request.headers.get("x-requested-with") or "").strip()
    if header == CSRF_HEADER_VALUE:
        return

    origin = request_origin(request)
    if origin and origin_allowed(origin):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF check failed")
