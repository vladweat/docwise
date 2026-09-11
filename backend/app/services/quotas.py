"""Organization plan limits. Quotas are commercial caps, not rate limits (429)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import NotFoundError, PaymentRequiredError
from app.core.time import utcnow_naive
from app.models.audit import RagAuditLog
from app.models.document import Document, DocumentStatus
from app.models.organization import Organization, OrganizationMembership, OrganizationPlan

QUOTA_EXCEEDED = "Organization quota exceeded"


class IngestionQuotaError(Exception):
    """Ingest would push indexed pages over the plan cap. Never mark the document `ready`."""

    def __init__(self, message: str = QUOTA_EXCEEDED) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class PlanLimits:
    seats: int
    pages: int
    chat_tokens: int
    sso: bool
    custom_domain: bool


def plan_limits(plan: str | None) -> PlanLimits:
    settings = get_settings()
    key = (plan or OrganizationPlan.starter.value).strip().lower()
    if key == OrganizationPlan.enterprise.value:
        return PlanLimits(
            seats=settings.plan_enterprise_seats,
            pages=settings.plan_enterprise_pages,
            chat_tokens=settings.plan_enterprise_tokens,
            sso=True,
            custom_domain=True,
        )
    if key == OrganizationPlan.team.value:
        return PlanLimits(
            seats=settings.plan_team_seats,
            pages=settings.plan_team_pages,
            chat_tokens=settings.plan_team_tokens,
            sso=False,
            custom_domain=False,
        )
    return PlanLimits(
        seats=settings.plan_starter_seats,
        pages=settings.plan_starter_pages,
        chat_tokens=settings.plan_starter_tokens,
        sso=False,
        custom_domain=False,
    )


def raise_quota_exceeded() -> None:
    raise PaymentRequiredError(QUOTA_EXCEEDED)


def lock_organization(db: Session, organization_id: UUID) -> Organization | None:
    return (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .with_for_update()
        .first()
    )


def ensure_billing_period(org: Organization) -> Organization:
    """Keep a current token window on the org row. Does not change plan or ACL."""
    now = utcnow_naive()
    days = max(int(get_settings().plan_period_days), 1)
    start = org.current_period_start
    end = org.current_period_end
    if start is None or end is None or now >= end:
        org.current_period_start = now
        org.current_period_end = now + timedelta(days=days)
    return org


def seat_count(db: Session, organization_id: UUID) -> int:
    value = (
        db.query(func.count(OrganizationMembership.id))
        .filter(OrganizationMembership.organization_id == organization_id)
        .scalar()
    )
    return int(value or 0)


def indexed_page_count(
    db: Session,
    organization_id: UUID,
    *,
    exclude_document_id: UUID | None = None,
) -> int:
    """Pages reserved by non-failed documents. Pending without total_pages counts as 1."""
    page_expr = func.coalesce(Document.total_pages, 1)
    query = db.query(func.coalesce(func.sum(page_expr), 0)).filter(
        Document.organization_id == organization_id,
        Document.status != DocumentStatus.failed.value,
    )
    if exclude_document_id is not None:
        query = query.filter(Document.id != exclude_document_id)
    return int(query.scalar() or 0)


def period_token_count(db: Session, org: Organization) -> int:
    ensure_billing_period(org)
    start = org.current_period_start
    end = org.current_period_end
    query = db.query(func.coalesce(func.sum(RagAuditLog.tokens_used), 0)).filter(
        RagAuditLog.organization_id == org.id,
        RagAuditLog.tokens_used.isnot(None),
    )
    if start is not None:
        query = query.filter(RagAuditLog.created_at >= start)
    if end is not None:
        query = query.filter(RagAuditLog.created_at < end)
    return int(query.scalar() or 0)


def usage_snapshot(db: Session, org: Organization) -> dict:
    limits = plan_limits(org.plan)
    ensure_billing_period(org)
    return {
        "plan": org.plan,
        "billing_status": org.billing_status,
        "limits": limits,
        "seats": seat_count(db, org.id),
        "pages": indexed_page_count(db, org.id),
        "chat_tokens": period_token_count(db, org),
        "current_period_start": org.current_period_start,
        "current_period_end": org.current_period_end,
    }


def enforce_page_quota_for_upload(
    db: Session,
    organization_id: UUID,
    incoming_pages: int,
) -> Organization:
    org = lock_organization(db, organization_id)
    if org is None:
        raise NotFoundError("Organization not found")
    limits = plan_limits(org.plan)
    used = indexed_page_count(db, organization_id)
    if used + max(int(incoming_pages), 0) > limits.pages:
        raise_quota_exceeded()
    return org


def assert_ingest_pages_allowed(
    db: Session,
    organization_id: UUID,
    incoming_pages: int,
    *,
    exclude_document_id: UUID,
) -> None:
    org = lock_organization(db, organization_id)
    if org is None:
        raise IngestionQuotaError()
    limits = plan_limits(org.plan)
    used = indexed_page_count(db, organization_id, exclude_document_id=exclude_document_id)
    if used + max(int(incoming_pages), 0) > limits.pages:
        raise IngestionQuotaError()


def enforce_seat_quota(db: Session, organization_id: UUID) -> None:
    org = lock_organization(db, organization_id)
    if org is None:
        raise_quota_exceeded()
    limits = plan_limits(org.plan)
    if seat_count(db, organization_id) >= limits.seats:
        raise_quota_exceeded()


def has_chat_token_quota(db: Session, org: Organization) -> bool:
    limits = plan_limits(org.plan)
    return period_token_count(db, org) < limits.chat_tokens
