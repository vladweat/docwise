import type {
  BillingSubscription,
  BillingUsage,
  ChangePlanResponse,
  DevSimulateAction,
  PlanName,
} from "@/types/billing";

import { apiFetch } from "./client";

export async function fetchBillingSubscription(): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/billing/subscription");
}

export async function fetchBillingUsage(): Promise<BillingUsage> {
  return apiFetch<BillingUsage>("/billing/usage");
}

export async function changeBillingPlan(plan: PlanName): Promise<ChangePlanResponse> {
  return apiFetch<ChangePlanResponse>("/billing/plan", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

export async function simulateDevBilling(
  action: DevSimulateAction,
  plan?: PlanName,
): Promise<BillingSubscription> {
  return apiFetch<BillingSubscription>("/billing/dev/simulate", {
    method: "POST",
    body: JSON.stringify(plan ? { action, plan } : { action }),
  });
}
