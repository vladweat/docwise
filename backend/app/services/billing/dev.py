"""Dev billing: org-admin writes plan / past_due / cancel with no money."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.billing import BillingProvider
from app.models.organization import BillingStatus, Organization, OrganizationPlan
from app.services.billing.port import PlanChangeResult, apply_subscription_state, remember_event
from app.services.quotas import ensure_billing_period


class DevBillingPort:
    provider = BillingProvider.dev.value

    def change_plan(self, db: Session, org: Organization, plan: str) -> PlanChangeResult:
        ensure_billing_period(org)
        apply_subscription_state(org, plan=plan, billing_status=BillingStatus.active.value)
        remember_event(
            db,
            organization_id=org.id,
            provider=self.provider,
            external_id=str(uuid4()),
            event_type="dev.plan",
            payload={"action": "set_plan", "plan": plan, "status": BillingStatus.active.value},
        )
        return PlanChangeResult()

    def simulate(
        self,
        db: Session,
        org: Organization,
        *,
        action: str,
        plan: str | None,
    ) -> Organization:
        ensure_billing_period(org)
        if action == "set_plan":
            target = plan or OrganizationPlan.starter.value
            apply_subscription_state(org, plan=target, billing_status=BillingStatus.active.value)
        elif action == "activate":
            apply_subscription_state(
                org,
                plan=plan or org.plan,
                billing_status=BillingStatus.active.value,
            )
        elif action == "past_due":
            apply_subscription_state(org, billing_status=BillingStatus.past_due.value)
        elif action == "cancel":
            apply_subscription_state(org, billing_status=BillingStatus.canceled.value)
        else:
            raise ValueError(action)
        remember_event(
            db,
            organization_id=org.id,
            provider=self.provider,
            external_id=str(uuid4()),
            event_type=f"dev.{action}",
            payload={"action": action, "plan": org.plan, "billing_status": org.billing_status},
        )
        return org
