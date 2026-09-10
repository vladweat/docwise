"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGate } from "@/components/auth-gate";
import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { canManageKnowledgeBase } from "@/lib/access-roles";
import { ApiRequestError, fetchBillingSubscription, fetchBillingUsage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { QuotaMeter } from "@/types/billing";

const PLAN_LABEL: Record<string, string> = {
  starter: "Starter",
  team: "Team",
  enterprise: "Enterprise",
};

function Meter({ label, meter }: { label: string; meter: QuotaMeter }) {
  const ratio = meter.limit > 0 ? Math.min(meter.used / meter.limit, 1) : 0;
  const exhausted = meter.used >= meter.limit;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className={exhausted ? "text-red-400" : "text-slate-400"}>
          {meter.used.toLocaleString("ru-RU")} / {meter.limit.toLocaleString("ru-RU")}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-800">
        <div
          className={exhausted ? "h-full bg-red-500" : "h-full bg-blue-500"}
          style={{ width: `${Math.max(ratio * 100, meter.used > 0 ? 4 : 0)}%` }}
        />
      </div>
    </div>
  );
}

export function SettingsPage() {
  const { user } = useAuth();
  const canManage = canManageKnowledgeBase(user);

  const usageQuery = useQuery({
    queryKey: ["billing-usage", user?.organization_id],
    queryFn: fetchBillingUsage,
    enabled: Boolean(user) && canManage,
  });
  const subQuery = useQuery({
    queryKey: ["billing-subscription", user?.organization_id],
    queryFn: fetchBillingSubscription,
    enabled: Boolean(user) && canManage,
  });

  return (
    <AuthGate>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-2xl space-y-4">
          <div>
            <h2 className="text-xl font-semibold">Настройки организации</h2>
            <p className="mt-1 text-sm text-slate-400">
              {user?.organization_name
                ? `План и квоты «${user.organization_name}».`
                : "План и квоты текущей организации."}
            </p>
          </div>

          {!canManage ? (
            <Card>
              <CardHeader>
                <CardTitle>Недостаточно прав</CardTitle>
                <CardDescription>
                  Просмотр плана и usage доступен только admin этой организации.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader className="flex flex-row items-start justify-between gap-3">
                  <div>
                    <CardTitle>Подписка</CardTitle>
                    <CardDescription>Квоты считаются по этой организации, не по аккаунту.</CardDescription>
                  </div>
                  {subQuery.data ? (
                    <Badge variant="secondary">{PLAN_LABEL[subQuery.data.plan] ?? subQuery.data.plan}</Badge>
                  ) : null}
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-slate-300">
                  {subQuery.isLoading ? <p className="text-slate-400">Загрузка…</p> : null}
                  {subQuery.error ? (
                    <p className="text-red-400">
                      {subQuery.error instanceof ApiRequestError
                        ? subQuery.error.message
                        : "Не удалось загрузить подписку"}
                    </p>
                  ) : null}
                  {subQuery.data ? (
                    <>
                      <p>
                        Статус биллинга:{" "}
                        <span className="text-slate-100">{subQuery.data.billing_status}</span>
                      </p>
                      {subQuery.data.current_period_end ? (
                        <p className="text-slate-400">
                          Период токенов до {formatDateTime(subQuery.data.current_period_end)}
                        </p>
                      ) : null}
                      <p className="text-xs text-slate-500">
                        SSO и свой домен — в плане Enterprise. Смена плана появится в следующем срезе.
                      </p>
                    </>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Использование</CardTitle>
                  <CardDescription>
                    Исчерпание квоты даёт отказ «квота организации исчерпана», без чужих файлов.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {usageQuery.isLoading ? <p className="text-sm text-slate-400">Загрузка…</p> : null}
                  {usageQuery.error ? (
                    <p className="text-sm text-red-400">
                      {usageQuery.error instanceof ApiRequestError
                        ? usageQuery.error.message
                        : "Не удалось загрузить usage"}
                    </p>
                  ) : null}
                  {usageQuery.data ? (
                    <>
                      <Meter label="Места" meter={usageQuery.data.seats} />
                      <Meter label="Проиндексированные страницы" meter={usageQuery.data.pages} />
                      <Meter label="Токены чата за период" meter={usageQuery.data.chat_tokens} />
                    </>
                  ) : null}
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </main>
    </AuthGate>
  );
}
