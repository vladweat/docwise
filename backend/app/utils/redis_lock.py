from functools import lru_cache
from uuid import UUID

import redis

from app.core.config import get_settings

LOCK_PREFIX = "indexing_lock"
DEFAULT_LOCK_TTL_SECONDS = 3600


def lock_key(document_id: str | UUID) -> str:
    return f"{LOCK_PREFIX}:{document_id}"


@lru_cache(maxsize=4)
def _redis_for_url(url: str) -> redis.Redis:
    return redis.from_url(url, decode_responses=True)


def get_redis_client() -> redis.Redis:
    return _redis_for_url(get_settings().redis_url)


def acquire_indexing_lock(document_id: str | UUID, ttl: int = DEFAULT_LOCK_TTL_SECONDS) -> bool:
    client = get_redis_client()
    return bool(client.set(lock_key(document_id), "1", nx=True, ex=ttl))


def release_indexing_lock(document_id: str | UUID) -> None:
    client = get_redis_client()
    client.delete(lock_key(document_id))


def is_indexing_locked(document_id: str | UUID) -> bool:
    client = get_redis_client()
    return client.exists(lock_key(document_id)) > 0
