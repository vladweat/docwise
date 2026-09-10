from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.organization import BillingStatus, OrganizationPlan


class PlanEntitlements(BaseModel):
    sso: bool
    custom_domain: bool


class BillingSubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: OrganizationPlan
    billing_status: BillingStatus
    current_period_start: datetime | None
    current_period_end: datetime | None
    entitlements: PlanEntitlements
    provider: str


class QuotaMeter(BaseModel):
    used: int
    limit: int


class BillingUsageResponse(BaseModel):
    plan: OrganizationPlan
    seats: QuotaMeter
    pages: QuotaMeter
    chat_tokens: QuotaMeter
    current_period_start: datetime | None
    current_period_end: datetime | None


class ChangePlanRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    plan: OrganizationPlan


class ChangePlanResponse(BaseModel):
    provider: str
    plan: OrganizationPlan | None = None
    billing_status: BillingStatus | None = None
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    entitlements: PlanEntitlements | None = None
    checkout_url: str | None = None


class DevSimulateAction(str, Enum):
    set_plan = "set_plan"
    past_due = "past_due"
    cancel = "cancel"
    activate = "activate"


class DevSimulateRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    action: DevSimulateAction
    plan: OrganizationPlan | None = None

    @model_validator(mode="after")
    def plan_required_for_set_plan(self) -> "DevSimulateRequest":
        if self.action == DevSimulateAction.set_plan and self.plan is None:
            raise ValueError("plan is required for set_plan")
        return self


def foreign_organization_id(body: BaseModel, current_org: UUID) -> UUID | None:
    extra = body.model_extra or {}
    raw = extra.get("organization_id") or extra.get("org_id")
    if raw is None:
        return None
    try:
        parsed = UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        return UUID("00000000-0000-0000-0000-000000000000")
    if parsed != current_org:
        return parsed
    return None
