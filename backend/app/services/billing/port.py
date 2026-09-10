"""Billing port: providers write org plan/status; quotas never call this."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.billing import BillingEvent, BillingProvider
from app.models.organization import BillingStatus, Organization, OrganizationPlan, OrganizationStatus

NOT_FOUND = "Not Found"
BILLING_UNAVAILABLE = "Billing provider is unavailable"


class BillingUnavailable(Exception):
    """Stripe keys missing or checkout cannot be created. HTTP 503."""


@dataclass(frozen=True)
class PlanChangeResult:
    checkout_url: str | None = None


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def apply_subscription_state(
    org: Organization,
    *,
    billing_status: str,
    plan: str | None = None,
) -> Organization:
    """Same transitions a webhook would write. Does not touch documents or chunks."""
    if plan is not None:
        org.plan = plan
    org.billing_status = billing_status
    if billing_status in {BillingStatus.past_due.value, BillingStatus.canceled.value}:
        org.status = OrganizationStatus.suspended.value
    elif billing_status == BillingStatus.active.value:
        org.status = OrganizationStatus.active.value
    return org


def sanitize_event_payload(payload: dict) -> dict:
    """Keep ids and status only — never chunk text, PDF bytes, or corpus keys."""
    allowed = (
        "id",
        "type",
        "action",
        "plan",
        "status",
        "customer",
        "subscription",
        "billing_status",
        "price_id",
    )
    return {key: payload[key] for key in allowed if key in payload and payload[key] is not None}


def remember_event(
    db: Session,
    *,
    organization_id: UUID,
    provider: str,
    external_id: str,
    event_type: str,
    payload: dict,
) -> bool:
    """Insert billing_events. False if (provider, external_id) already exists."""
    event = BillingEvent(
        organization_id=organization_id,
        provider=provider,
        external_id=external_id,
        event_type=event_type,
        payload=sanitize_event_payload(payload),
        processed_at=_utcnow(),
    )
    try:
        with db.begin_nested():
            db.add(event)
            db.flush()
        return True
    except IntegrityError:
        return False


def parse_plan(value: str | None) -> str | None:
    if value is None:
        return None
    key = value.strip().lower()
    allowed = {item.value for item in OrganizationPlan}
    if key not in allowed:
        return None
    return key


def get_billing_port():
    from app.core.config import get_settings
    from app.services.billing.dev import DevBillingPort
    from app.services.billing.stripe_adapter import StripeBillingPort

    if get_settings().billing_provider_name == BillingProvider.stripe.value:
        return StripeBillingPort()
    return DevBillingPort()


def billing_readiness() -> str:
    """Value for GET /ready. `dev` is healthy; stripe without keys is not ok."""
    from app.core.config import get_settings

    settings = get_settings()
    provider = settings.billing_provider_name
    if provider == BillingProvider.dev.value:
        return BillingProvider.dev.value
    if provider == BillingProvider.stripe.value:
        return "ok" if settings.stripe_configured else "error"
    return "error"
