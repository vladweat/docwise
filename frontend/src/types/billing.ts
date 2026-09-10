export type PlanName = "starter" | "team" | "enterprise";
export type BillingStatus = "active" | "past_due" | "canceled";

export interface PlanEntitlements {
  sso: boolean;
  custom_domain: boolean;
}

export interface BillingSubscription {
  plan: PlanName;
  billing_status: BillingStatus;
  current_period_start: string | null;
  current_period_end: string | null;
  entitlements: PlanEntitlements;
}

export interface QuotaMeter {
  used: number;
  limit: number;
}

export interface BillingUsage {
  plan: PlanName;
  seats: QuotaMeter;
  pages: QuotaMeter;
  chat_tokens: QuotaMeter;
  current_period_start: string | null;
  current_period_end: string | null;
}
