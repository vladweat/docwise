"""Fixed-window Redis rate limits. Infra, not a domain service."""

import logging
from typing import cast

import redis
from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


def client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(scope: str, key: str | int, limit: int) -> None:
    """Fixed-window Redis limiter. limit<=0 disables. Redis errors fail open."""
    if limit <= 0:
        return

    redis_key = f"rl:{scope}:{key}"
    try:
        client = get_redis_client()
        count = int(cast(int, client.incr(redis_key)))
        if count == 1:
            client.expire(redis_key, WINDOW_SECONDS)
        ttl = int(cast(int, client.ttl(redis_key) or WINDOW_SECONDS))
    except redis.RedisError as exc:
        logger.warning("Rate limit Redis failed, allowing request: %s", exc)
        return

    if count > limit:
        retry_after = str(max(ttl, 1))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": retry_after},
        )


def enforce_auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    enforce_rate_limit("auth", client_ip(request), settings.rate_limit_auth_per_minute)
