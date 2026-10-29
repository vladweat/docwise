"""Redis client, session store, and indexing lock. Infra, not a domain service."""

from contextvars import ContextVar
from functools import lru_cache
import logging
from typing import cast
from uuid import UUID, uuid4

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

LOCK_PREFIX = "indexing_lock"
DEFAULT_LOCK_TTL_SECONDS = 3600

_RELEASE_OWNED_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""
_LOCK_OWNERS: ContextVar[dict[str, str]] = ContextVar("docwise_indexing_lock_owners", default={})


def lock_key(document_id: str | UUID) -> str:
    return f"{LOCK_PREFIX}:{document_id}"


@lru_cache(maxsize=4)
def _redis_for_url(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)


def get_redis_client() -> redis.Redis:
    return _redis_for_url(get_settings().redis_url)


def acquire_indexing_lock(
    document_id: str | UUID,
    ttl: int = DEFAULT_LOCK_TTL_SECONDS,
    *,
    owner_token: str | None = None,
) -> bool:
    """NX lock per document UUID with an owner token for safe release."""
    client = get_redis_client()
    key = lock_key(document_id)
    token = owner_token or uuid4().hex
    previous_token = _LOCK_OWNERS.get().get(key)
    if previous_token is not None:
        # Celery can retry in the same worker context after a transient release error.
        release_indexing_lock(document_id, previous_token)
    acquired = bool(client.set(key, token, nx=True, ex=ttl))
    if acquired:
        owners = dict(_LOCK_OWNERS.get())
        owners[key] = token
        _LOCK_OWNERS.set(owners)
    return acquired


def release_indexing_lock(document_id: str | UUID, owner_token: str | None = None) -> bool:
    """Delete a lock only if it still belongs to this execution."""
    key = lock_key(document_id)
    token = owner_token or _LOCK_OWNERS.get().get(key)
    if token is None:
        return False
    try:
        client = get_redis_client()
        released = bool(client.eval(_RELEASE_OWNED_LOCK_SCRIPT, 1, key, token))
    except redis.RedisError as exc:
        logger.warning("Could not release ingestion lock (error_type=%s)", type(exc).__name__)
        return False
    owners = dict(_LOCK_OWNERS.get())
    if owners.get(key) == token:
        owners.pop(key)
        _LOCK_OWNERS.set(owners)
    return released


def is_indexing_locked(document_id: str | UUID) -> bool:
    client = get_redis_client()
    return int(cast(int, client.exists(lock_key(document_id)))) > 0
