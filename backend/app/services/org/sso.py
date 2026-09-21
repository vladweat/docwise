"""SSO / SAML. Org comes from the connector slug, never from the assertion."""

from __future__ import annotations

from uuid import UUID

from pydantic import ValidationError
from redis import RedisError
from sqlalchemy.orm import Session

from app.api import API_V1
from app.core.config import get_settings
from app.core.errors import BadRequestError, ForbiddenError, UnauthorizedError, UnavailableError
from app.core.principal import Principal
from app.models.organization import (
    Organization,
    OrganizationInvite,
    OrganizationStatus,
)
from app.models.sso import OrganizationSsoConnection
from app.models.user import User, UserRole
from app.schemas.sso import SsoAttributeMap
from app.services.org.quotas import plan_limits
from app.services.org.tenancy import (
    accept_invite,
    add_membership,
    get_membership,
    principal_from_parts,
)
from app.core.redis import get_redis_client

SSO_NOT_FOUND = "Not found"
SSO_REQUIRED = "SSO sign-in required"
SSO_NOT_IN_PLAN = "SSO is not included in the current plan"
SSO_INVITE_REQUIRED = "SSO access requires an invitation"
SSO_FRESH_PREFIX = "sso_fresh:"

ROLE_RANK = {
    UserRole.employee.value: 0,
    UserRole.manager.value: 1,
    UserRole.admin.value: 2,
}


def sso_paths(slug: str) -> tuple[str, str]:
    return f"{API_V1}/auth/sso/{slug}/login", f"{API_V1}/auth/sso/{slug}/acs"


def sso_fresh_ttl_seconds() -> int:
    return max(int(get_settings().sso_fresh_ttl_seconds), 60)


def mark_sso_fresh(user_id: UUID, organization_id: UUID) -> None:
    ttl = sso_fresh_ttl_seconds()
    try:
        get_redis_client().set(f"{SSO_FRESH_PREFIX}{user_id}:{organization_id}", "1", ex=ttl)
    except RedisError as exc:
        raise UnavailableError("Session store unavailable") from exc


def has_sso_fresh(user_id: UUID, organization_id: UUID) -> bool:
    try:
        stored = get_redis_client().get(f"{SSO_FRESH_PREFIX}{user_id}:{organization_id}")
    except RedisError as exc:
        raise UnavailableError("Session store unavailable") from exc
    return bool(stored)


def session_allowed_for_org(organization: Organization, *, sso_claim: bool) -> bool:
    if not organization.sso_enforced:
        return True
    return sso_claim is True


def parse_attribute_map(raw: dict | SsoAttributeMap | None) -> dict:
    if isinstance(raw, SsoAttributeMap):
        return raw.model_dump(mode="json")
    try:
        return SsoAttributeMap.model_validate(raw or {}).model_dump(mode="json")
    except ValidationError as exc:
        raise BadRequestError("Invalid attribute_map") from exc


def map_idp_groups(attribute_map: dict | None, groups: list[str]) -> tuple[str, list[str], bool]:
    parsed = SsoAttributeMap.model_validate(attribute_map or {})
    incoming = {item.strip().lower() for item in groups if item and item.strip()}
    role = parsed.default_role.value
    departments = list(parsed.default_departments)
    matched = False
    best = ROLE_RANK.get(role, 0)
    for rule in parsed.rules:
        if rule.group not in incoming:
            continue
        matched = True
        if rule.role is not None and ROLE_RANK.get(rule.role.value, -1) >= best:
            role = rule.role.value
            best = ROLE_RANK[rule.role.value]
        for dept in rule.departments:
            if dept not in departments:
                departments.append(dept)
    return role, departments, matched


def connection_for_org(db: Session, organization_id: UUID) -> OrganizationSsoConnection | None:
    return (
        db.query(OrganizationSsoConnection)
        .filter(OrganizationSsoConnection.organization_id == organization_id)
        .first()
    )


def public_sso_target(db: Session, slug: str) -> tuple[Organization, OrganizationSsoConnection] | None:
    """Resolve `{slug}` → connector org. Missing, suspended, or no entitlement → None (404)."""
    cleaned = (slug or "").strip().lower()
    if not cleaned:
        return None
    organization = db.query(Organization).filter(Organization.slug == cleaned).first()
    if organization is None:
        return None
    connection = connection_for_org(db, organization.id)
    if connection is None:
        return None
    if organization.status != OrganizationStatus.active.value:
        return None
    if not plan_limits(organization.plan).sso:
        return None
    return organization, connection


def require_sso_entitlement(organization: Organization) -> None:
    if not plan_limits(organization.plan).sso:
        raise ForbiddenError(SSO_NOT_IN_PLAN)


def _pending_invite(db: Session, organization_id: UUID, email: str) -> OrganizationInvite | None:
    return (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == organization_id,
            OrganizationInvite.email == email,
            OrganizationInvite.accepted_at.is_(None),
        )
        .first()
    )


def complete_sso_login(
    db: Session,
    organization: Organization,
    connection: OrganizationSsoConnection,
    *,
    email: str,
    groups: list[str],
) -> Principal:
    normalized = email.strip().lower()
    user = db.query(User).filter(User.email == normalized).first()
    role, departments, matched = map_idp_groups(connection.attribute_map, groups)
    membership = get_membership(db, user.id, organization.id) if user is not None else None

    if membership is None:
        if connection.jit_enabled:
            if user is None:
                user = User(email=normalized, hashed_password=None)
                db.add(user)
                db.flush()
            membership = add_membership(
                db,
                organization=organization,
                user=user,
                role=role,
                departments=departments,
            )
        else:
            invite = _pending_invite(db, organization.id, normalized)
            if invite is None:
                raise ForbiddenError(SSO_INVITE_REQUIRED)
            if user is None:
                user = User(email=normalized, hashed_password=None)
                db.add(user)
                db.flush()
            membership = accept_invite(db, invite, user)
            if matched:
                membership.role = role
                membership.departments = departments
    elif matched:
        membership.role = role
        membership.departments = departments

    if user is None or not user.is_active:
        raise UnauthorizedError("Account is inactive")
    return principal_from_parts(user, membership, organization)
