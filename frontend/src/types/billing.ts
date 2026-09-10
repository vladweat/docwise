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
  provider: "dev" | "stripe";
}

export type DevSimulateAction = "set_plan" | "past_due" | "cancel" | "activate";

export interface ChangePlanResponse {
  provider: "dev" | "stripe";
  plan?: PlanName | null;
  billing_status?: BillingStatus | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  entitlements?: PlanEntitlements | null;
  checkout_url?: string | null;
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
