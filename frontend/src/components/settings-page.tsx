"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { canManageKnowledgeBase } from "@/lib/access-roles";
import {
  ApiRequestError,
  changeBillingPlan,
  fetchBillingSubscription,
  fetchBillingUsage,
  fetchOrganizationSso,
  simulateDevBilling,
  upsertOrganizationSso,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { PlanName, QuotaMeter } from "@/types/billing";
import type { SsoAttributeMap } from "@/types/sso";
import { useToastStore } from "@/stores/toast-store";

const PLAN_LABEL: Record<PlanName, string> = {
  starter: "Starter",
  team: "Team",
  enterprise: "Enterprise",
};

const PLANS: PlanName[] = ["starter", "team", "enterprise"];

const DEFAULT_ATTRIBUTE_MAP: SsoAttributeMap = {
  default_role: "employee",
  default_departments: [],
  rules: [],
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
  const { user, refreshUser } = useAuth();
  const canManage = canManageKnowledgeBase(user);
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const [draftPlan, setDraftPlan] = useState<PlanName | "">("");
  const [idpEntityId, setIdpEntityId] = useState("");
  const [jitEnabled, setJitEnabled] = useState(false);
  const [ssoEnforced, setSsoEnforced] = useState(false);
  const [attributeMapText, setAttributeMapText] = useState(
    JSON.stringify(DEFAULT_ATTRIBUTE_MAP, null, 2),
  );
  const [ssoFormReady, setSsoFormReady] = useState(false);

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
  const ssoEnabled = subQuery.data?.entitlements.sso === true;
  const ssoQuery = useQuery({
    queryKey: ["org-sso", user?.organization_id],
    queryFn: fetchOrganizationSso,
    enabled: Boolean(user) && canManage && ssoEnabled,
  });

  useEffect(() => {
    setSsoFormReady(false);
  }, [user?.organization_id]);

  useEffect(() => {
    if (!ssoQuery.data || ssoFormReady) return;
    setIdpEntityId(ssoQuery.data.idp_entity_id ?? "");
    setJitEnabled(ssoQuery.data.jit_enabled);
    setSsoEnforced(ssoQuery.data.sso_enforced);
    setAttributeMapText(JSON.stringify(ssoQuery.data.attribute_map ?? DEFAULT_ATTRIBUTE_MAP, null, 2));
    setSsoFormReady(true);
  }, [ssoQuery.data, ssoFormReady]);

  const selectedPlan = draftPlan || subQuery.data?.plan || "starter";
  const isDev = subQuery.data?.provider === "dev";

  const invalidateBilling = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["billing-usage"] }),
      queryClient.invalidateQueries({ queryKey: ["billing-subscription"] }),
    ]);
  };

  const planMutation = useMutation({
    mutationFn: () => changeBillingPlan(selectedPlan),
    onSuccess: async (result) => {
      if (result.checkout_url) {
        window.location.assign(result.checkout_url);
        return;
      }
      pushToast(`План: ${PLAN_LABEL[result.plan ?? selectedPlan]}`, "info");
      setDraftPlan("");
      await invalidateBilling();
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось сменить план";
      pushToast(message, "error");
    },
  });

  const simulateMutation = useMutation({
    mutationFn: (action: "activate" | "past_due" | "cancel") => simulateDevBilling(action),
    onSuccess: async (sub) => {
      if (sub.billing_status === "past_due" || sub.billing_status === "canceled") {
        pushToast("Организация приостановлена (как при past_due / отмене)", "info");
        await refreshUser();
        return;
      }
      pushToast("Подписка активна", "info");
      await invalidateBilling();
    },
    onError: (err) => {
      if (err instanceof ApiRequestError && err.status === 401) {
        void refreshUser();
        return;
      }
      const message = err instanceof ApiRequestError ? err.message : "Не удалось изменить биллинг";
      pushToast(message, "error");
    },
  });

  const ssoMutation = useMutation({
    mutationFn: () => {
      let attribute_map: SsoAttributeMap;
      try {
        attribute_map = JSON.parse(attributeMapText) as SsoAttributeMap;
      } catch {
        throw new ApiRequestError("Некорректный JSON маппинга групп", 400);
      }
      return upsertOrganizationSso({
        protocol: "saml",
        idp_entity_id: idpEntityId.trim() || null,
        idp_metadata: { kind: "dev" },
        jit_enabled: jitEnabled,
        attribute_map,
        sso_enforced: ssoEnforced,
      });
    },
    onSuccess: async (result) => {
      pushToast(result.sso_enforced ? "SSO сохранён, вход только через IdP" : "SSO сохранён", "info");
      await queryClient.invalidateQueries({ queryKey: ["org-sso"] });
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось сохранить SSO";
      pushToast(message, "error");
    },
  });

  const busy = planMutation.isPending || simulateMutation.isPending || ssoMutation.isPending;

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
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    {isDev ? <Badge variant="warning">Dev billing</Badge> : null}
                    {subQuery.data ? (
                      <Badge variant="secondary">{PLAN_LABEL[subQuery.data.plan] ?? subQuery.data.plan}</Badge>
                    ) : null}
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-slate-300">
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
                        SSO и свой домен — в плане Enterprise. Смена плана не открывает чужую организацию.
                      </p>
                      <div className="space-y-2 border-t border-slate-800 pt-3">
                        <Label htmlFor="plan-select">План</Label>
                        <select
                          id="plan-select"
                          className="flex h-9 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 outline-none focus:border-blue-500"
                          value={selectedPlan}
                          disabled={busy}
                          onChange={(event) => setDraftPlan(event.target.value as PlanName)}
                        >
                          {PLANS.map((plan) => (
                            <option key={plan} value={plan}>
                              {PLAN_LABEL[plan]}
                            </option>
                          ))}
                        </select>
                        <Button
                          type="button"
                          size="sm"
                          disabled={busy || selectedPlan === subQuery.data.plan}
                          onClick={() => planMutation.mutate()}
                        >
                          {isDev ? "Применить план" : "Checkout"}
                        </Button>
                      </div>
                      {isDev ? (
                        <div className="flex flex-wrap gap-2 border-t border-slate-800 pt-3">
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() => simulateMutation.mutate("activate")}
                          >
                            Активировать
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => simulateMutation.mutate("past_due")}
                          >
                            Просрочить
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="destructive"
                            disabled={busy}
                            onClick={() => simulateMutation.mutate("cancel")}
                          >
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

              <Card>
                <CardHeader>
                  <CardTitle>SSO / SAML</CardTitle>
                  <CardDescription>
                    Коннектор принадлежит этой организации. Org берётся из slug, не из assertion.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-slate-300">
                  {!ssoEnabled ? (
                    <p className="text-slate-400">SSO входит в план Enterprise. Смена плана не открывает чужую организацию.</p>
                  ) : null}
                  {ssoEnabled && ssoQuery.isLoading ? <p className="text-slate-400">Загрузка…</p> : null}
                  {ssoEnabled && ssoQuery.error ? (
                    <p className="text-red-400">
                      {ssoQuery.error instanceof ApiRequestError
                        ? ssoQuery.error.message
                        : "Не удалось загрузить SSO"}
                    </p>
                  ) : null}
                  {ssoEnabled && ssoQuery.data ? (
                    <>
                      <p className="text-xs text-slate-500">
                        Login: <code className="text-slate-300">{ssoQuery.data.login_path}</code>
                        <br />
                        ACS: <code className="text-slate-300">{ssoQuery.data.acs_path}</code>
                        {ssoQuery.data.slug ? (
                          <>
                            <br />
                            Slug: <code className="text-slate-300">{ssoQuery.data.slug}</code>
                          </>
                        ) : null}
                      </p>
                      <div>
                        <Label htmlFor="idp-entity">IdP entity ID</Label>
                        <Input
                          id="idp-entity"
                          className="mt-1"
                          value={idpEntityId}
                          onChange={(event) => setIdpEntityId(event.target.value)}
                          placeholder="https://idp.example/metadata"
                          disabled={busy}
                        />
                      </div>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={jitEnabled}
                          onChange={(event) => setJitEnabled(event.target.checked)}
                          disabled={busy}
                        />
                        JIT: создавать membership только в этой org
                      </label>
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={ssoEnforced}
                          onChange={(event) => setSsoEnforced(event.target.checked)}
                          disabled={busy}
                        />
                        Требовать SSO (пароль и Google не входят в эту org)
                      </label>
                      <div>
                        <Label htmlFor="attr-map">Маппинг групп IdP → role / departments</Label>
                        <textarea
                          id="attr-map"
                          className="mt-1 min-h-32 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-blue-500"
                          value={attributeMapText}
                          onChange={(event) => setAttributeMapText(event.target.value)}
                          disabled={busy}
                          spellCheck={false}
                        />
                      </div>
                      <Button type="button" size="sm" disabled={busy} onClick={() => ssoMutation.mutate()}>
                        Сохранить SSO
                      </Button>
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
