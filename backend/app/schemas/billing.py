from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
