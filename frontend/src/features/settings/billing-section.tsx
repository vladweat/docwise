"use client";

import { useMutation } from "@tanstack/react-query";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { BillingSubscription, BillingUsage, PlanName, QuotaMeter } from "@/types/billing";

const PLAN_LABEL: Record<PlanName, string> = {
  starter: "Starter",
  team: "Team",
  enterprise: "Enterprise",
};

const PLANS: PlanName[] = ["starter", "team", "enterprise"];

export function Meter({ label, meter }: { label: string; meter: QuotaMeter }) {
  const ratio = meter.limit > 0 ? Math.min(meter.used / meter.limit, 1) : 0;
  const exhausted = meter.used >= meter.limit;
  const value = Math.max(ratio * 100, meter.used > 0 ? 4 : 0);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className={exhausted ? "text-red-400" : "text-slate-400"}>
          {meter.used.toLocaleString("ru-RU")} / {meter.limit.toLocaleString("ru-RU")}
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
  const isDev = sub?.provider === "dev";
  return (
    <>
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>Подписка</CardTitle>
            <CardDescription>Квоты считаются по этой организации, не по аккаунту.</CardDescription>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {isDev ? <Badge variant="warning">Dev billing</Badge> : null}
            {sub ? <Badge variant="secondary">{PLAN_LABEL[sub.plan] ?? sub.plan}</Badge> : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-slate-300">
          {subLoading ? <Skeleton className="h-4 w-40" /> : null}
          {subError ? (
            <Alert variant="destructive">
              {subError instanceof ApiRequestError ? subError.message : "Не удалось загрузить подписку"}
            </Alert>
          ) : null}
          {sub ? (
            <>
              <p>
                Статус биллинга: <span className="text-slate-100">{sub.billing_status}</span>
              </p>
              {sub.current_period_end ? (
                <p className="text-slate-400">Период токенов до {formatDateTime(sub.current_period_end)}</p>
              ) : null}
              <p className="text-xs text-slate-500">
                SSO и свой домен — в плане Enterprise. Смена плана не открывает чужую организацию.
              </p>
              <div className="space-y-2 border-t border-slate-800 pt-3">
                <Label htmlFor="plan-select">План</Label>
                <Select value={selectedPlan} disabled={busy} onValueChange={(value) => onPlanChange(value as PlanName)}>
                  <SelectTrigger id="plan-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PLANS.map((plan) => (
                      <SelectItem key={plan} value={plan}>
                        {PLAN_LABEL[plan]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button type="button" size="sm" disabled={busy || selectedPlan === sub.plan} onClick={onChangePlan}>
                  {isDev ? "Применить план" : "Checkout"}
                </Button>
              </div>
              {isDev ? (
                <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-3">
                  <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => onSimulate("activate")}>
                    Активировать
                  </Button>
                  <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => onSimulate("past_due")}>
                    Просрочить
                  </Button>
                  <Button type="button" size="sm" variant="destructive" disabled={busy} onClick={() => onSimulate("cancel")}>
                    Отменить
                  </Button>
                  <p className="basis-full text-xs text-slate-500">
                    Просрочка и отмена приостанавливают вход в эту организацию.
                  </p>
                </div>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Использование</CardTitle>
          <CardDescription>Исчерпание квоты даёт отказ «квота организации исчерпана», без чужих файлов.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {usageLoading ? <Skeleton className="h-4 w-48" /> : null}
          {usageError ? (
            <Alert variant="destructive">
              {usageError instanceof ApiRequestError ? usageError.message : "Не удалось загрузить usage"}
            </Alert>
          ) : null}
          {usage ? (
            <>
              <Meter label="Места" meter={usage.seats} />
              <Meter label="Проиндексированные страницы" meter={usage.pages} />
              <Meter label="Токены чата за период" meter={usage.chat_tokens} />
            </>
          ) : null}
        </CardContent>
      </Card>
    </>
  );
}

export { PLAN_LABEL };
