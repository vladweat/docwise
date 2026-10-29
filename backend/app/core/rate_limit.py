"""Fixed-window Redis rate limits. Infra, not a domain service."""

import logging
from ipaddress import ip_address
from typing import cast

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


def client_ip(request: Request, *, trust_forwarded_for: bool = False) -> str:
    if trust_forwarded_for:
        forwarded = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
        if forwarded:
            try:
                return str(ip_address(forwarded))
            except ValueError:
                logger.warning("Ignoring invalid X-Forwarded-For value")
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(scope: str, key: str | int, limit: int) -> None:
    """Fixed-window Redis limiter. limit<=0 disables; Redis errors fail closed."""
    if limit <= 0:
        return

    redis_key = f"rl:{scope}:{key}"
    try:
        client = get_redis_client()
        count = int(cast(int, client.incr(redis_key)))
        ttl = int(cast(int, client.ttl(redis_key) or 0))
        if count == 1 or ttl < 0:
            client.expire(redis_key, WINDOW_SECONDS)
            ttl = WINDOW_SECONDS
        elif ttl == 0:
            ttl = WINDOW_SECONDS
    except redis.RedisError as exc:
        logger.error(
            "Rate limit Redis unavailable (scope=%s, error_type=%s)",
            scope,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiter unavailable",
        ) from exc

    if count > limit:
        retry_after = str(max(ttl, 1))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": retry_after},
        )


def enforce_auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit(
        "auth",
        client_ip(request, trust_forwarded_for=settings.rate_limit_trust_x_forwarded_for),
        settings.rate_limit_auth_per_minute,
    )
