"""Redis LLM cache keyed by org, index generation, and allowed_roles.

Generation lives on `organizations.llm_index_generation`. Bump it (and drop
matching Redis keys) when the visible corpus changes: PATCH ACL, DELETE, ready ingest.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.redis import get_redis_client
from app.models.organization import Organization

logger = logging.getLogger(__name__)

CACHE_VERSION = "v4"
LLM_CACHE_TTL_SECONDS = 86400
SCAN_COUNT = 200


def canonical_allowed_roles(roles: Sequence[str]) -> tuple[str, ...]:
    """Stable, sorted unique roles for cache keys and ACL. Never from the request body."""
    return tuple(sorted({str(role).strip() for role in roles if str(role).strip()}))


def question_hash(question: str) -> str:
    return hashlib.sha256(f"{CACHE_VERSION}\n{question.strip()}".encode("utf-8")).hexdigest()


def cache_key(
    question: str,
    allowed_roles: Sequence[str],
    *,
    organization_id: UUID,
    index_generation: int = 0,
) -> str:
    """Redis key scoped by org, corpus generation, and membership roles — never share across tenants."""
    roles = canonical_allowed_roles(allowed_roles)
    roles_hash = hashlib.sha256(",".join(roles).encode("utf-8")).hexdigest()[:16]
    return (
        f"llm_cache:{CACHE_VERSION}:{organization_id}:{int(index_generation)}:"
        f"{roles_hash}:{question_hash(question)}"
    )


def org_cache_pattern(organization_id: UUID) -> str:
    return f"llm_cache:{CACHE_VERSION}:{organization_id}:*"


def redis_get(key: str) -> dict | None:
    try:
        value = get_redis_client().get(key)
    except Exception as exc:
        logger.warning("Redis cache get failed error_type=%s", type(exc).__name__)
        return None
    if not value:
        return None
    try:
        parsed = json.loads(cast(str, value))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def redis_set(key: str, payload: dict[str, Any]) -> None:
    try:
        get_redis_client().set(key, json.dumps(payload, ensure_ascii=False), ex=LLM_CACHE_TTL_SECONDS)
    except Exception as exc:
        logger.warning("Redis cache set failed error_type=%s", type(exc).__name__)


def delete_org_cache_keys(organization_id: UUID) -> None:
    pattern = org_cache_pattern(organization_id)
    try:
        client = get_redis_client()
        cursor = 0
        while True:
            cursor, keys = cast(
                tuple[int, list[str]],
                client.scan(cursor=cursor, match=pattern, count=SCAN_COUNT),
            )
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.warning(
            "Redis cache invalidate failed org_id=%s error_type=%s",
            organization_id,
            type(exc).__name__,
        )


def bump_llm_index_generation(db: Session, organization_id: UUID) -> int:
    org = db.get(Organization, organization_id)
    if org is None:
        return 0
    org.llm_index_generation = int(org.llm_index_generation or 0) + 1
    db.flush()
    return org.llm_index_generation


def invalidate_llm_cache(db: Session, organization_id: UUID) -> int:
    """Bump org generation and drop Redis keys. Caller commits the generation bump."""
    generation = bump_llm_index_generation(db, organization_id)
    delete_org_cache_keys(organization_id)
    return generation
