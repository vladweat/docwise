from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.principal import Principal
from app.schemas.billing import (
    BillingSubscriptionResponse,
    BillingUsageResponse,
    PlanEntitlements,
    QuotaMeter,
)
from app.services.quotas import ensure_billing_period, plan_limits, usage_snapshot

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/subscription", response_model=BillingSubscriptionResponse)
def get_subscription(
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> BillingSubscriptionResponse:
    org = current_user.organization
    ensure_billing_period(org)
    db.add(org)
    db.commit()
    db.refresh(org)
    limits = plan_limits(org.plan)
    return BillingSubscriptionResponse(
        plan=org.plan,
        billing_status=org.billing_status,
        current_period_start=org.current_period_start,
        current_period_end=org.current_period_end,
        entitlements=PlanEntitlements(sso=limits.sso, custom_domain=limits.custom_domain),
    )


@router.get("/usage", response_model=BillingUsageResponse)
def get_usage(
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> BillingUsageResponse:
    org = current_user.organization
    snapshot = usage_snapshot(db, org)
    db.add(org)
    db.commit()
    limits = snapshot["limits"]
    return BillingUsageResponse(
        plan=snapshot["plan"],
        seats=QuotaMeter(used=snapshot["seats"], limit=limits.seats),
        pages=QuotaMeter(used=snapshot["pages"], limit=limits.pages),
        chat_tokens=QuotaMeter(used=snapshot["chat_tokens"], limit=limits.chat_tokens),
        current_period_start=snapshot["current_period_start"],
        current_period_end=snapshot["current_period_end"],
    )
