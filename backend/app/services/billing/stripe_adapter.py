"""Stripe adapter. Live api.stripe.com is not an M6 acceptance criterion."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.billing import BillingProvider
from app.models.organization import BillingStatus, Organization, OrganizationPlan
from app.services.billing.port import (
    BillingUnavailable,
    PlanChangeResult,
    apply_subscription_state,
    parse_plan,
    remember_event,
)

logger = logging.getLogger(__name__)

STRIPE_API = "https://api.stripe.com/v1"
SIGNATURE_TOLERANCE_SECONDS = 300
HANDLED_TYPES = {
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
}


def verify_stripe_signature(payload: bytes, header: str, secret: str, *, now: int | None = None) -> bool:
    """HMAC as in Stripe docs. Does not call the network."""
    if not secret or not header:
        return False
    items = {part.split("=", 1)[0]: part.split("=", 1)[1] for part in header.split(",") if "=" in part}
    timestamp = items.get("t")
    signature = items.get("v1")
    if not timestamp or not signature:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    from time import time as _time

    current = int(_time() if now is None else now)
    if abs(current - ts) > SIGNATURE_TOLERANCE_SECONDS:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def sanitize_stripe_object(data: dict) -> dict:
    obj = data.get("object") if isinstance(data.get("object"), dict) else data
    price_id = None
    items = obj.get("items") if isinstance(obj, dict) else None
    if isinstance(items, dict):
        records = items.get("data") or []
        if records and isinstance(records[0], dict):
            price = records[0].get("price") or {}
            if isinstance(price, dict):
                price_id = price.get("id")
            elif isinstance(price, str):
                price_id = price
    parent = obj.get("parent") if isinstance(obj, dict) else None
    subscription = obj.get("subscription") if isinstance(obj, dict) else None
    if subscription is None and isinstance(parent, dict):
        subscription_details = parent.get("subscription_details") or {}
        subscription = subscription_details.get("subscription")
    return {
        "id": data.get("id") or (obj.get("id") if isinstance(obj, dict) else None),
        "type": data.get("type"),
        "status": obj.get("status") if isinstance(obj, dict) else None,
        "customer": obj.get("customer") if isinstance(obj, dict) else None,
        "subscription": subscription if isinstance(subscription, str) else None,
        "price_id": price_id,
    }


class StripeBillingPort:
    provider = BillingProvider.stripe.value

    def change_plan(self, db: Session, org: Organization, plan: str) -> PlanChangeResult:
        settings = get_settings()
        if not settings.stripe_secret_key.strip():
            raise BillingUnavailable()
        price_id = settings.stripe_price_id(plan)
        if not price_id:
            raise BillingUnavailable()
        url = self._create_checkout_session(org, plan=plan, price_id=price_id)
        return PlanChangeResult(checkout_url=url)

    def _create_checkout_session(self, org: Organization, *, plan: str, price_id: str) -> str:
        settings = get_settings()
        base = settings.public_frontend_url()
        form: dict[str, str] = {
            "mode": "subscription",
            "success_url": f"{base}/settings?checkout=success",
            "cancel_url": f"{base}/settings?checkout=cancel",
            "client_reference_id": str(org.id),
            "metadata[organization_id]": str(org.id),
            "metadata[plan]": plan,
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": "1",
        }
        if org.stripe_customer_id:
            form["customer"] = org.stripe_customer_id
        try:
            response = httpx.post(
                f"{STRIPE_API}/checkout/sessions",
                data=form,
                auth=(settings.stripe_secret_key.strip(), ""),
                timeout=15.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("Stripe checkout failed: %s", exc)
            raise BillingUnavailable() from exc
        if response.status_code >= 400:
            logger.warning("Stripe checkout HTTP %s", response.status_code)
            raise BillingUnavailable()
        url = response.json().get("url")
        if not isinstance(url, str) or not url:
            raise BillingUnavailable()
        return url

    def handle_webhook(self, db: Session, payload: bytes, signature_header: str) -> None:
        settings = get_settings()
        secret = settings.stripe_webhook_secret.strip()
        if not secret:
            raise LookupError("adapter disabled")
        if not verify_stripe_signature(payload, signature_header, secret):
            raise ValueError("invalid signature")
        try:
            event = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid payload") from exc
        if not isinstance(event, dict):
            raise ValueError("invalid payload")
        event_id = str(event.get("id") or "")
        event_type = str(event.get("type") or "")
        if not event_id or event_type not in HANDLED_TYPES:
            return
        data_object = (event.get("data") or {}).get("object") if isinstance(event.get("data"), dict) else None
        if not isinstance(data_object, dict):
            return
        org = self._resolve_org(db, event_type, data_object)
        if org is None:
            logger.info("Stripe event %s: no organization", event_id)
            return
        if not remember_event(
            db,
            organization_id=org.id,
            provider=self.provider,
            external_id=event_id,
            event_type=event_type,
            payload=sanitize_stripe_object({"id": event_id, "type": event_type, "object": data_object}),
        ):
            return
        self._apply_event(org, event_type, data_object)
        db.add(org)

    def _resolve_org(self, db: Session, event_type: str, obj: dict) -> Organization | None:
        customer = obj.get("customer")
        subscription = obj.get("subscription")
        if event_type.startswith("customer.subscription"):
            subscription = obj.get("id") or subscription
        if isinstance(customer, str) and customer:
            found = (
                db.query(Organization)
                .filter(Organization.stripe_customer_id == customer)
                .first()
            )
            if found is not None:
                return found
        if isinstance(subscription, str) and subscription:
            found = (
                db.query(Organization)
                .filter(Organization.stripe_subscription_id == subscription)
                .first()
            )
            if found is not None:
                return found
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        raw_org = metadata.get("organization_id")
        if not raw_org:
            return None
        try:
            org_id = UUID(str(raw_org))
        except (ValueError, TypeError, AttributeError):
            return None
        return db.get(Organization, org_id)

    def _apply_event(self, org: Organization, event_type: str, obj: dict) -> None:
        customer = obj.get("customer")
        if isinstance(customer, str) and customer:
            org.stripe_customer_id = customer
        subscription_id = obj.get("id") if event_type.startswith("customer.subscription") else obj.get("subscription")
        if isinstance(subscription_id, str) and subscription_id:
            org.stripe_subscription_id = subscription_id

        if event_type == "invoice.paid":
            apply_subscription_state(org, billing_status=BillingStatus.active.value)
            return
        if event_type == "invoice.payment_failed":
            apply_subscription_state(org, billing_status=BillingStatus.past_due.value)
            return
        if event_type == "customer.subscription.deleted":
            apply_subscription_state(org, billing_status=BillingStatus.canceled.value)
            return

        stripe_status = str(obj.get("status") or "")
        plan = self._plan_from_subscription(obj)
        if stripe_status in {"active", "trialing"}:
            apply_subscription_state(
                org,
                plan=plan or org.plan,
                billing_status=BillingStatus.active.value,
            )
        elif stripe_status in {"past_due", "unpaid"}:
            apply_subscription_state(org, billing_status=BillingStatus.past_due.value)
        elif stripe_status in {"canceled", "incomplete_expired"}:
            apply_subscription_state(org, billing_status=BillingStatus.canceled.value)

    def _plan_from_subscription(self, obj: dict) -> str | None:
        settings = get_settings()
        metadata = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
        from_meta = parse_plan(str(metadata.get("plan") or "") or None)
        if from_meta:
            return from_meta
        items = obj.get("items") if isinstance(obj.get("items"), dict) else {}
        records = items.get("data") or []
        if not records or not isinstance(records[0], dict):
            return None
        price = records[0].get("price") or {}
        price_id = price.get("id") if isinstance(price, dict) else price
        if not isinstance(price_id, str):
            return None
        reverse = {
            settings.stripe_price_starter.strip(): OrganizationPlan.starter.value,
            settings.stripe_price_team.strip(): OrganizationPlan.team.value,
            settings.stripe_price_enterprise.strip(): OrganizationPlan.enterprise.value,
        }
        reverse.pop("", None)
        return reverse.get(price_id)
