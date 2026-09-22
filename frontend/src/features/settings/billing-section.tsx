"use client";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/i18n/locale-provider";
import { ApiRequestError } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
import { formatDateTime } from "@/lib/format";
import type { BillingSubscription, BillingUsage, PlanName, QuotaMeter } from "@/types/billing";

const PLAN_MESSAGE_KEY: Record<PlanName, "settings.planStarter" | "settings.planTeam" | "settings.planEnterprise"> = {
  starter: "settings.planStarter",
  team: "settings.planTeam",
  enterprise: "settings.planEnterprise",
};

const PLANS: PlanName[] = ["starter", "team", "enterprise"];

export function planDisplayLabel(t: (key: "settings.planStarter" | "settings.planTeam" | "settings.planEnterprise") => string, plan: PlanName): string {
  return t(PLAN_MESSAGE_KEY[plan]);
}

export function Meter({ label, meter }: { label: string; meter: QuotaMeter }) {
  const { locale } = useI18n();
  const numberLocale = locale === "ru" ? "ru-RU" : "en-US";
  const ratio = meter.limit > 0 ? Math.min(meter.used / meter.limit, 1) : 0;
  const exhausted = meter.used >= meter.limit;
  const value = Math.max(ratio * 100, meter.used > 0 ? 4 : 0);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className={exhausted ? "text-red-400" : "text-slate-400"}>
          {meter.used.toLocaleString(numberLocale)} / {meter.limit.toLocaleString(numberLocale)}
        </span>
      </div>
      <Progress value={value} indicatorClassName={exhausted ? "bg-red-500" : "bg-blue-500"} />
    </div>
  );
}

export function BillingSection({
  sub,
  usage,
  subLoading,
  usageLoading,
  subError,
  usageError,
  selectedPlan,
  onPlanChange,
  busy,
  onChangePlan,
  onSimulate,
}: {
  sub?: BillingSubscription;
  usage?: BillingUsage;
  subLoading: boolean;
  usageLoading: boolean;
  subError: unknown;
  usageError: unknown;
  selectedPlan: PlanName;
  onPlanChange: (plan: PlanName) => void;
  busy: boolean;
  onChangePlan: () => void;
  onSimulate: (action: "activate" | "past_due" | "cancel") => void;
}) {
  const { t } = useI18n();
  const isDev = sub?.provider === "dev";
  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>{t("settings.billingTitle")}</CardTitle>
            <CardDescription>{t("settings.billingDescription")}</CardDescription>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {isDev ? <Badge variant="warning">{t("settings.devBillingBadge")}</Badge> : null}
            {sub ? (
              <Badge variant="secondary">{planDisplayLabel(t, sub.plan)}</Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-slate-300">
          {subLoading ? <Skeleton className="h-4 w-40" /> : null}
          {subError ? (
            <Alert variant="destructive">
              {subError instanceof ApiRequestError
                ? userFacingApiMessage(subError.status, subError.message)
                : t("errors.loadSubscriptionFailed")}
            </Alert>
          ) : null}
          {sub ? (
            <>
              <p>
                {t("settings.billingStatus")}{" "}
                <span className="text-slate-100">{sub.billing_status}</span>
              </p>
              {sub.current_period_end ? (
                <p className="text-slate-400">
                  {t("settings.tokenPeriod", { date: formatDateTime(sub.current_period_end) })}
                </p>
              ) : null}
              <p className="text-xs text-slate-500">{t("settings.enterpriseNote")}</p>
              <div className="space-y-2 border-t border-slate-800 pt-3">
                <Label htmlFor="plan-select">{t("settings.planLabel")}</Label>
                <Select value={selectedPlan} disabled={busy} onValueChange={(value) => onPlanChange(value as PlanName)}>
                  <SelectTrigger id="plan-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PLANS.map((plan) => (
                      <SelectItem key={plan} value={plan}>
                        {planDisplayLabel(t, plan)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button type="button" size="sm" disabled={busy || selectedPlan === sub.plan} onClick={onChangePlan}>
                  {isDev ? t("settings.applyPlan") : t("settings.checkout")}
                </Button>
              </div>
              {isDev ? (
                <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-3">
                  <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => onSimulate("activate")}>
                    {t("settings.activate")}
                  </Button>
                  <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onSimulate("past_due")}>
                    {t("settings.pastDue")}
                  </Button>
                  <Button type="button" size="sm" variant="destructive" disabled={busy} onClick={() => onSimulate("cancel")}>
                    {t("settings.cancel")}
                  </Button>
                  <p className="basis-full text-xs text-slate-500">{t("settings.billingDevNote")}</p>
                </div>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("settings.usageTitle")}</CardTitle>
          <CardDescription>{t("settings.usageDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {usageLoading ? <Skeleton className="h-4 w-48" /> : null}
          {usageError ? (
            <Alert variant="destructive">
              {usageError instanceof ApiRequestError
                ? userFacingApiMessage(usageError.status, usageError.message)
                : t("errors.loadUsageFailed")}
            </Alert>
          ) : null}
          {usage ? (
            <>
              <Meter label={t("settings.meterSeats")} meter={usage.seats} />
              <Meter label={t("settings.meterPages")} meter={usage.pages} />
              <Meter label={t("settings.meterChatTokens")} meter={usage.chat_tokens} />
            </>
          ) : null}
        </CardContent>
      </Card>
    </>
  );
}

