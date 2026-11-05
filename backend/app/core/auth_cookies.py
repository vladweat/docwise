"""Issue and revoke `dw_*` session cookies (host-only, ADR-015)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException, Response, status
from jwt.exceptions import InvalidTokenError
from redis import RedisError

from app.core.config import get_settings
from app.core.redis import get_redis_client

ACCESS_COOKIE = "dw_access"
REFRESH_COOKIE = "dw_refresh"
REFRESH_PREFIX = "refresh:"


def cookie_params() -> dict:
    """Host-only cookies: never set Domain (ADR-015). A parent Domain= would leak Acme's cookie onto Globex."""
    settings = get_settings()
    samesite = (settings.cookie_samesite or "lax").strip().lower()
    if samesite not in {"lax", "strict", "none"}:
        samesite = "lax"
    secure = bool(settings.cookie_secure)
    if samesite == "none":
        secure = True
    return {
        "httponly": True,
        "secure": secure,
        "samesite": samesite,
        "path": "/",
    }


def create_refresh_token(
    subject: str,
    *,
    org_id: str | None = None,
    sso: bool = False,
) -> str:
    """Rotate refresh JWT; store jti in Redis. Optional org_id and SSO claim mirror access token."""
    settings = get_settings()
    jti = uuid4().hex
    expire = datetime.now(UTC) + timedelta(minutes=settings.refresh_token_expire_minutes)
    payload = {"sub": subject, "exp": expire, "typ": "refresh", "jti": jti}
    if org_id:
        payload["org_id"] = org_id
    if sso:
        payload["sso"] = True
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    ttl = settings.refresh_token_expire_minutes * 60
    try:
        get_redis_client().set(f"{REFRESH_PREFIX}{jti}", subject, ex=ttl)
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session store unavailable",
        ) from exc
    return token


def decode_refresh_token(token: str) -> dict:
    """Verify refresh JWT and Redis jti binding."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except InvalidTokenError as exc:
        raise ValueError("Invalid token") from exc
    if payload.get("typ") != "refresh":
        raise ValueError("Invalid token")
    jti = payload.get("jti")
    email = payload.get("sub")
    if not jti or not email:
        raise ValueError("Invalid token")
    try:
        stored = get_redis_client().get(f"{REFRESH_PREFIX}{jti}")
    except RedisError as exc:
        raise ValueError("Invalid token") from exc
    if stored != email:
        raise ValueError("Invalid token")
    return payload


def revoke_refresh_token(token: str) -> None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        jti = payload.get("jti")
        if jti:
            get_redis_client().delete(f"{REFRESH_PREFIX}{jti}")
    except (InvalidTokenError, RedisError, ValueError):
        return


def set_auth_cookies(response: Response, *, access_token: str, refresh_token: str) -> None:
    """Apply `cookie_params()` (host-only, no `Domain=`)."""
    settings = get_settings()
    params = cookie_params()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **params,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_expire_minutes * 60,
        **params,
    )


def clear_auth_cookies(response: Response) -> None:
    """Delete `dw_access` and `dw_refresh` with the same flags used at issue time."""
    params = cookie_params()
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        response.delete_cookie(
            name,
            path=params["path"],
            samesite=params["samesite"],
            secure=params["secure"],
            httponly=params["httponly"],
        )
