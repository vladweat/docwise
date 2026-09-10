"""Organization plan limits. Quotas are commercial caps, not rate limits (429)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.chat import RagAuditLog
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


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
    raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=QUOTA_EXCEEDED)


def ensure_billing_period(org: Organization) -> Organization:
    """Keep a current token window on the org row. Does not change plan or ACL."""
    now = _utcnow()
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
    query = db.query(func.coalesce(func.sum(Document.total_pages), 0)).filter(
        Document.organization_id == organization_id,
        Document.status != DocumentStatus.failed.value,
        Document.total_pages.isnot(None),
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


def enforce_page_quota_for_upload(db: Session, organization_id: UUID) -> None:
    org = db.get(Organization, organization_id)
    if org is None:
        raise_quota_exceeded()
    limits = plan_limits(org.plan)
    if indexed_page_count(db, organization_id) >= limits.pages:
        raise_quota_exceeded()


def assert_ingest_pages_allowed(
    db: Session,
    organization_id: UUID,
    incoming_pages: int,
    *,
    exclude_document_id: UUID,
) -> None:
    org = db.get(Organization, organization_id)
    if org is None:
        raise IngestionQuotaError()
    limits = plan_limits(org.plan)
    used = indexed_page_count(db, organization_id, exclude_document_id=exclude_document_id)
    if used + max(int(incoming_pages), 0) > limits.pages:
        raise IngestionQuotaError()


def enforce_seat_quota(db: Session, organization_id: UUID) -> None:
    org = db.get(Organization, organization_id)
    if org is None:
        raise_quota_exceeded()
    limits = plan_limits(org.plan)
    if seat_count(db, organization_id) >= limits.seats:
        raise_quota_exceeded()


def has_chat_token_quota(db: Session, org: Organization) -> bool:
    limits = plan_limits(org.plan)
    return period_token_count(db, org) < limits.chat_tokens
