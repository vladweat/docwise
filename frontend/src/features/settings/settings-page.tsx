"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { AuthGate } from "@/features/auth/auth-gate";
import { useAuth } from "@/features/auth/auth-provider";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/fade-in";
import { BillingSection, PLAN_LABEL } from "@/features/settings/billing-section";
import { DomainSection } from "@/features/settings/domain-section";
import { SsoSection } from "@/features/settings/sso-section";
import { canManageOrganization } from "@/lib/access-roles";
import {
  ApiRequestError,
  changeBillingPlan,
  fetchBillingSubscription,
  fetchBillingUsage,
  fetchOrganizationDomain,
  fetchOrganizationSso,
  simulateDevBilling,
  upsertOrganizationDomain,
  upsertOrganizationSso,
  verifyOrganizationDomain,
} from "@/lib/api";
import type { PlanName } from "@/types/billing";
import type { SsoAttributeMap } from "@/types/sso";
import { useToastStore } from "@/stores/toast-store";

const DEFAULT_ATTRIBUTE_MAP: SsoAttributeMap = {
  default_role: "employee",
  default_departments: [],
  rules: [],
};

export function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const canManage = canManageOrganization(user);
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
  const [customHostname, setCustomHostname] = useState("");

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
  const domainQuery = useQuery({
    queryKey: ["org-domain", user?.organization_id],
    queryFn: fetchOrganizationDomain,
    enabled: Boolean(user) && canManage,
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

  useEffect(() => {
    if (!domainQuery.data) return;
    setCustomHostname(domainQuery.data.custom_hostname ?? "");
  }, [domainQuery.data]);

  const selectedPlan = draftPlan || subQuery.data?.plan || "starter";

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

  const domainMutation = useMutation({
    mutationFn: () => upsertOrganizationDomain(customHostname.trim() || null),
    onSuccess: async (result) => {
      const saved = customHostname.trim().toLowerCase();
      if (result.platform_hostnames.includes(saved)) {
        pushToast("Это платформенный хост этой организации, он уже привязан.", "info");
        setCustomHostname(result.custom_hostname ?? "");
      } else {
        pushToast("Домен сохранён. Неподтверждённый hostname не пинит сессию.", "info");
      }
      await queryClient.invalidateQueries({ queryKey: ["org-domain"] });
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось сохранить домен";
      pushToast(message, "error");
    },
  });

  const verifyDomainMutation = useMutation({
    mutationFn: () => {
      const token = domainQuery.data?.verification_token;
      if (!token) throw new ApiRequestError("Нет токена проверки", 400);
      return verifyOrganizationDomain(token);
    },
    onSuccess: async () => {
      pushToast("Домен подтверждён", "info");
      await queryClient.invalidateQueries({ queryKey: ["org-domain"] });
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось подтвердить домен";
      pushToast(message, "error");
    },
  });

  const busy =
    planMutation.isPending ||
    simulateMutation.isPending ||
    ssoMutation.isPending ||
    domainMutation.isPending ||
    verifyDomainMutation.isPending;

  return (
    <AuthGate>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <FadeIn className="mx-auto max-w-2xl space-y-4">
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
                  Просмотр плана и usage доступен только admin этой организации. Manager управляет базой знаний, не
                  биллингом.
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <>
              <BillingSection
                sub={subQuery.data}
                usage={usageQuery.data}
                subLoading={subQuery.isLoading}
                usageLoading={usageQuery.isLoading}
                subError={subQuery.error}
                usageError={usageQuery.error}
                selectedPlan={selectedPlan}
                onPlanChange={setDraftPlan}
                busy={busy}
                onChangePlan={() => planMutation.mutate()}
                onSimulate={(action) => simulateMutation.mutate(action)}
              />
              <SsoSection
                enabled={ssoEnabled}
                connection={ssoQuery.data}
                loading={ssoQuery.isLoading}
                error={ssoQuery.error}
                idpEntityId={idpEntityId}
                jitEnabled={jitEnabled}
                ssoEnforced={ssoEnforced}
                attributeMapText={attributeMapText}
                busy={busy}
                onIdpChange={setIdpEntityId}
                onJitChange={setJitEnabled}
                onEnforcedChange={setSsoEnforced}
                onMapChange={setAttributeMapText}
                onSave={() => ssoMutation.mutate()}
              />
              <DomainSection
                domain={domainQuery.data}
                loading={domainQuery.isLoading}
                error={domainQuery.error}
                customHostname={customHostname}
                busy={busy}
                onHostnameChange={setCustomHostname}
                onSave={() => domainMutation.mutate()}
                onVerify={() => verifyDomainMutation.mutate()}
              />
            </>
          )}
        </FadeIn>
      </main>
    </AuthGate>
  );
}
