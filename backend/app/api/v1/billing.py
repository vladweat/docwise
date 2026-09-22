"""Plans, usage, and dev simulate for the current org only."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import get_current_user, get_db, require_admin
from app.core.principal import Principal
from app.models.billing import BillingProvider, BillingStatus
from app.models.organization import OrganizationPlan
from app.models.user import UserRole
from app.schemas.billing import (
    BillingSubscriptionResponse,
    BillingUsageResponse,
    ChangePlanRequest,
    ChangePlanResponse,
    DevSimulateRequest,
    PlanEntitlements,
    QuotaMeter,
)
from app.schemas.common import foreign_organization_id
from app.services.billing import (
    BILLING_UNAVAILABLE,
    NOT_FOUND,
    BillingUnavailable,
    get_billing_port,
)
from app.services.org.quotas import ensure_billing_period, plan_limits, usage_snapshot

router = APIRouter(prefix="/billing", tags=["billing"])


def _subscription_payload(org, provider: str) -> BillingSubscriptionResponse:
    limits = plan_limits(org.plan)
    return BillingSubscriptionResponse(
        plan=org.plan,
        billing_status=org.billing_status,
        current_period_start=org.current_period_start,
        current_period_end=org.current_period_end,
        entitlements=PlanEntitlements(sso=limits.sso, custom_domain=limits.custom_domain),
        provider=provider,
    )


def require_dev_billing_admin(current_user: Principal = Depends(get_current_user)) -> Principal:
    if get_settings().billing_provider_name != BillingProvider.dev.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    if current_user.role != UserRole.admin.value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    return current_user


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
    return _subscription_payload(org, get_settings().billing_provider_name)


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


@router.post("/plan", response_model=ChangePlanResponse)
def change_plan(
    body: ChangePlanRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_admin),
) -> ChangePlanResponse:
    if foreign_organization_id(body, current_user.organization_id) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    org = current_user.organization
    provider = get_settings().billing_provider_name
    port = get_billing_port()
    try:
        result = port.change_plan(db, org, body.plan.value)
    except BillingUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=BILLING_UNAVAILABLE,
        ) from exc
    db.add(org)
    db.commit()
    db.refresh(org)
    if result.checkout_url:
        return ChangePlanResponse(provider=provider, checkout_url=result.checkout_url)
    return ChangePlanResponse(
        provider=provider,
        plan=OrganizationPlan(org.plan),
        billing_status=BillingStatus(org.billing_status),
        current_period_start=org.current_period_start,
        current_period_end=org.current_period_end,
        entitlements=_subscription_payload(org, provider).entitlements,
    )


@router.post("/dev/simulate", response_model=BillingSubscriptionResponse)
def simulate_dev_billing(
    body: DevSimulateRequest,
    db: Session = Depends(get_db),
    current_user: Principal = Depends(require_dev_billing_admin),
) -> BillingSubscriptionResponse:
    if foreign_organization_id(body, current_user.organization_id) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    org = current_user.organization
    port = get_billing_port()
    simulate = getattr(port, "simulate", None)
    if simulate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    simulate(db, org, action=body.action.value, plan=body.plan.value if body.plan else None)
    db.add(org)
    db.commit()
    db.refresh(org)
    return _subscription_payload(org, BillingProvider.dev.value)


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    if settings.billing_provider_name != BillingProvider.stripe.value or not settings.stripe_webhook_secret.strip():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    payload = await request.body()
    signature = request.headers.get("stripe-signature") or ""
    port = get_billing_port()
    handle = getattr(port, "handle_webhook", None)
    if handle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    try:
        handle(db, payload, signature)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature") from exc
    db.commit()
    return {"received": True}
