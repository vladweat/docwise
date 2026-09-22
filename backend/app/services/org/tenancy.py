"""Organizations, memberships, and invites. Tenant id never comes from a request body."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    GoneError,
    NotFoundError,
    UnavailableError,
    UnprocessableError,
)
from app.core.principal import Principal
from app.core.time import utcnow_naive
from app.models.billing import BillingStatus
from app.models.organization import (
    Organization,
    OrganizationInvite,
    OrganizationMembership,
    OrganizationPlan,
    OrganizationStatus,
)
from app.services.org.domains import attach_platform_domains
from app.models.user import User, UserRole
from app.schemas.user import OrganizationSummary, UserResponse
from app.services.org.quotas import enforce_seat_quota

INVITE_TTL = timedelta(days=14)
ORG_NAME_MIN = 1
ORG_NAME_MAX = 200
SLUG_MAX = 80
NOT_FOUND_ORG = "Organization not found"


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def slugify_org_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[: SLUG_MAX - 9]
    return slug or "org"


def normalize_org_name(name: str) -> str:
    cleaned = " ".join((name or "").split())
    if len(cleaned) < ORG_NAME_MIN or len(cleaned) > ORG_NAME_MAX:
        raise UnprocessableError("Invalid organization_name")
    return cleaned


def _new_org_period() -> tuple[datetime, datetime]:
    now = utcnow_naive()
    days = max(int(get_settings().plan_period_days), 1)
    return now, now + timedelta(days=days)


def create_organization(db: Session, name: str) -> Organization:
    cleaned = normalize_org_name(name)
    base = slugify_org_name(cleaned)
    period_start, period_end = _new_org_period()
    for _ in range(8):
        slug = f"{base}-{secrets.token_hex(3)}"[:SLUG_MAX]
        org = Organization(
            name=cleaned,
            slug=slug,
            status=OrganizationStatus.active.value,
            plan=OrganizationPlan.starter.value,
            billing_status=BillingStatus.active.value,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        try:
            with db.begin_nested():
                db.add(org)
                db.flush()
                attach_platform_domains(db, org)
            return org
        except IntegrityError:
            continue
    raise UnavailableError("Could not allocate organization slug")


def add_membership(
    db: Session,
    *,
    organization: Organization,
    user: User,
    role: str,
    departments: list[str] | None = None,
) -> OrganizationMembership:
    enforce_seat_quota(db, organization.id)
    membership = OrganizationMembership(
        organization_id=organization.id,
        user_id=user.id,
        role=role,
        departments=list(departments or []),
    )
    db.add(membership)
    db.flush()
    return membership


def get_membership(db: Session, user_id: UUID, organization_id: UUID) -> OrganizationMembership | None:
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.organization_id == organization_id,
        )
        .first()
    )


def first_membership(db: Session, user_id: UUID) -> OrganizationMembership | None:
    return (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user_id)
        .order_by(OrganizationMembership.created_at.asc(), OrganizationMembership.id.asc())
        .first()
    )


def first_password_membership(db: Session, user_id: UUID) -> OrganizationMembership | None:
    """Skip SSO-enforced orgs so password/Google cannot land there."""
    return (
        db.query(OrganizationMembership)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(
            OrganizationMembership.user_id == user_id,
            Organization.sso_enforced.is_(False),
            Organization.status == OrganizationStatus.active.value,
        )
        .order_by(OrganizationMembership.created_at.asc(), OrganizationMembership.id.asc())
        .first()
    )


def principal_from_parts(
    user: User,
    membership: OrganizationMembership,
    organization: Organization,
) -> Principal:
    return Principal(user=user, membership=membership, organization=organization)


def resolve_principal(
    db: Session,
    user: User,
    organization_id: UUID | None,
) -> Principal | None:
    """Map JWT org_id (or first membership) to Principal; org id never taken from request body."""
    if not user.is_active:
        return None
    membership: OrganizationMembership | None
    if organization_id is not None:
        membership = get_membership(db, user.id, organization_id)
    else:
        membership = first_membership(db, user.id)
    if membership is None:
        return None
    organization = db.get(Organization, membership.organization_id)
    if organization is None:
        return None
    if organization.status != OrganizationStatus.active.value:
        return None
    return principal_from_parts(user, membership, organization)


def resolve_principal_for_password(
    db: Session,
    user: User,
    organization_id: UUID | None,
) -> Principal | None:
    if not user.is_active:
        return None
    if organization_id is not None:
        membership = get_membership(db, user.id, organization_id)
        if membership is not None:
            organization = db.get(Organization, membership.organization_id)
            if (
                organization is not None
                and organization.status == OrganizationStatus.active.value
                and not organization.sso_enforced
            ):
                return principal_from_parts(user, membership, organization)
    membership = first_password_membership(db, user.id)
    if membership is None:
        return None
    organization = db.get(Organization, membership.organization_id)
    if organization is None or organization.status != OrganizationStatus.active.value:
        return None
    return principal_from_parts(user, membership, organization)


def user_response(db: Session, principal: Principal) -> UserResponse:
    rows = (
        db.query(OrganizationMembership, Organization)
        .join(Organization, Organization.id == OrganizationMembership.organization_id)
        .filter(OrganizationMembership.user_id == principal.id)
        .order_by(Organization.name.asc(), OrganizationMembership.created_at.asc())
        .all()
    )
    return UserResponse(
        id=principal.id,
        email=principal.email,
        role=principal.role,
        departments=principal.departments,
        is_active=principal.is_active,
        created_at=principal.created_at,
        organization_id=principal.organization_id,
        organization_name=principal.organization_name,
        organizations=[
            OrganizationSummary(
                id=org.id,
                name=org.name,
                role=membership.role,
                departments=list(membership.departments or []),
            )
            for membership, org in rows
        ],
    )


def create_invite(
    db: Session,
    *,
    organization: Organization,
    email: str,
    role: str,
    departments: list[str],
    invited_by: User,
) -> tuple[OrganizationInvite, str]:
    if role not in {item.value for item in UserRole}:
        raise BadRequestError("Invalid role")
    normalized_email = email.strip().lower()
    pending = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == organization.id,
            OrganizationInvite.email == normalized_email,
            OrganizationInvite.accepted_at.is_(None),
        )
        .first()
    )
    if pending is not None:
        raise ConflictError("An invite for this email is already pending")
    enforce_seat_quota(db, organization.id)
    token = secrets.token_urlsafe(32)
    invite = OrganizationInvite(
        organization_id=organization.id,
        email=normalized_email,
        role=role,
        departments=list(departments),
        token_hash=hash_invite_token(token),
        invited_by_user_id=invited_by.id,
        expires_at=utcnow_naive() + INVITE_TTL,
    )
    db.add(invite)
    db.flush()
    return invite, token


def get_pending_invite(db: Session, token: str) -> OrganizationInvite:
    invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.token_hash == hash_invite_token(token),
            OrganizationInvite.accepted_at.is_(None),
        )
        .first()
    )
    if invite is None:
        raise NotFoundError("Invite not found")
    now = utcnow_naive()
    if invite.expires_at < now:
        raise GoneError("Invite expired")
    return invite


def accept_invite(db: Session, invite: OrganizationInvite, user: User) -> OrganizationMembership:
    if user.email.strip().lower() != invite.email.strip().lower():
        raise ForbiddenError("Invite email mismatch")
    existing = get_membership(db, user.id, invite.organization_id)
    if existing is not None:
        invite.accepted_at = utcnow_naive()
        db.flush()
        return existing
    organization = db.get(Organization, invite.organization_id)
    if organization is None or organization.status != OrganizationStatus.active.value:
        raise NotFoundError(NOT_FOUND_ORG)
    membership = add_membership(
        db,
        organization=organization,
        user=user,
        role=invite.role,
        departments=list(invite.departments or []),
    )
    invite.accepted_at = utcnow_naive()
    db.flush()
    return membership


def list_members(db: Session, organization_id: UUID) -> list[tuple[OrganizationMembership, User]]:
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.created_at.asc(), User.email.asc())
        .all()
    )
    return [(membership, user) for membership, user in rows]
