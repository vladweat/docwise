"""Shared HTTP helpers. Not a tenant source — extras are rejected, never trusted."""

from uuid import UUID

from pydantic import BaseModel


def foreign_organization_id(body: BaseModel, current_org: UUID) -> UUID | None:
    extra = body.model_extra or {}
    raw = extra.get("organization_id") or extra.get("org_id")
    if raw is None:
        return None
    try:
        parsed = UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return UUID("00000000-0000-0000-0000-000000000000")
    if parsed != current_org:
        return parsed
    return None
