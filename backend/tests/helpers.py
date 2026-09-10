"""Shared pytest helpers for tenancy-aware fixtures."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.principal import Principal
from app.models.organization import Organization, OrganizationMembership, OrganizationPlan, OrganizationStatus
from app.models.user import User, UserRole

WIPE_SQL = """
TRUNCATE TABLE
    billing_events,
    rag_audit_logs,
    chat_messages,
    chat_sessions,
    document_chunks,
    documents,
    organization_sso_connections,
    organization_invites,
    organization_memberships,
    users,
    organizations
RESTART IDENTITY CASCADE
"""


def wipe_app_tables(db: Session) -> None:
    db.execute(text(WIPE_SQL))
    db.commit()


def register_payload(
    email: str,
    password: str = "securepass123",
    *,
    organization_name: str | None = None,
    invite_token: str | None = None,
) -> dict:
    payload: dict = {"email": email, "password": password}
    if invite_token:
        payload["invite_token"] = invite_token
    else:
        payload["organization_name"] = organization_name or f"Org {email.split('@')[0]}"
    return payload


def set_membership(
    db: Session,
    email: str,
    *,
    role: str,
    departments: list[str] | None = None,
) -> None:
    user = db.query(User).filter(User.email == email).first()
    assert user is not None
    membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user.id)
        .order_by(OrganizationMembership.created_at.asc())
        .first()
    )
    assert membership is not None
    membership.role = role
    membership.departments = departments or []
    db.commit()


def set_org_plan(db: Session, organization_id, plan: str) -> None:
    org = db.get(Organization, organization_id)
    assert org is not None
    org.plan = plan
    db.commit()


def make_org(db: Session, name: str | None = None) -> Organization:
    org = Organization(
        name=name or f"Org {uuid4().hex[:8]}",
        slug=f"org-{uuid4().hex[:12]}",
        status=OrganizationStatus.active.value,
        plan=OrganizationPlan.starter.value,
    )
    db.add(org)
    db.flush()
    return org


def make_principal(
    db: Session,
    org: Organization,
    *,
    role: str = UserRole.employee.value,
    departments: list[str] | None = None,
    email: str | None = None,
) -> Principal:
    user = User(
        email=email or f"user-{uuid4().hex[:10]}@example.com",
        hashed_password="hashed",
        is_active=True,
    )
    db.add(user)
    db.flush()
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=role,
        departments=departments or [],
    )
    db.add(membership)
    db.flush()
    return Principal(user=user, membership=membership, organization=org)
