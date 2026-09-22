"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { AuthGate } from "@/features/auth/auth-gate";
import { useAuth } from "@/features/auth/auth-provider";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/fade-in";
import { BillingSection, planDisplayLabel } from "@/features/settings/billing-section";
import { DomainSection } from "@/features/settings/domain-section";
import { SsoSection } from "@/features/settings/sso-section";
import { TeamSection } from "@/features/settings/team-section";
import { canManageOrganization } from "@/lib/access-roles";
import {
  ApiRequestError,
  changeBillingPlan,
  fetchBillingSubscription,
  fetchBillingUsage,
  fetchOrganizationDomain,
  fetchOrganizationMembers,
  fetchOrganizationSso,
  simulateDevBilling,
  upsertOrganizationDomain,
  upsertOrganizationSso,
  verifyOrganizationDomain,
} from "@/lib/api";
import type { PlanName } from "@/types/billing";
import type { SsoAttributeMap } from "@/types/sso";
import { useI18n } from "@/i18n/locale-provider";
import { userFacingApiMessage } from "@/lib/quota";
import { useToastStore } from "@/stores/toast-store";

const DEFAULT_ATTRIBUTE_MAP: SsoAttributeMap = {
  default_role: "employee",
  default_departments: [],
  rules: [],
};

export function SettingsPage() {
  const { t } = useI18n();
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

  const membersQuery = useQuery({
    queryKey: ["org-members", user?.organization_id],
    queryFn: fetchOrganizationMembers,
    enabled: Boolean(user) && canManage,
  });
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
      pushToast(
        t("settings.planChanged", {
          plan: planDisplayLabel(t, (result.plan ?? selectedPlan) as PlanName),
        }),
        "info",
      );
      setDraftPlan("");
      await invalidateBilling();
    },
    onError: (err) => {
      const message =
        err instanceof ApiRequestError
          ? userFacingApiMessage(err.status, err.message)
          : t("errors.changePlanFailed");
      pushToast(message, "error");
    },
  });

  const simulateMutation = useMutation({
    mutationFn: (action: "activate" | "past_due" | "cancel") => simulateDevBilling(action),
    onSuccess: async (sub) => {
      if (sub.billing_status === "past_due" || sub.billing_status === "canceled") {
        pushToast(t("settings.orgSuspended"), "info");
        await refreshUser();
        return;
      }
      pushToast(t("settings.subscriptionActive"), "info");
      await invalidateBilling();
    },
    onError: (err) => {
      if (err instanceof ApiRequestError && err.status === 401) {
        void refreshUser();
        return;
      }
      const message =
        err instanceof ApiRequestError
          ? userFacingApiMessage(err.status, err.message)
          : t("errors.billingSimulateFailed");
      pushToast(message, "error");
    },
  });

  const ssoMutation = useMutation({
    mutationFn: () => {
      let attribute_map: SsoAttributeMap;
      try {
        attribute_map = JSON.parse(attributeMapText) as SsoAttributeMap;
      } catch {
        throw new ApiRequestError(t("errors.ssoJsonInvalid"), 400);
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
      pushToast(
        result.sso_enforced ? t("settings.ssoSavedEnforced") : t("settings.ssoSaved"),
        "info",
      );
      await queryClient.invalidateQueries({ queryKey: ["org-sso"] });
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : t("errors.saveSsoFailed");
      pushToast(message, "error");
    },
  });

  const domainMutation = useMutation({
    mutationFn: () => upsertOrganizationDomain(customHostname.trim() || null),
    onSuccess: async (result) => {
      const saved = customHostname.trim().toLowerCase();
      if (result.platform_hostnames.includes(saved)) {
        pushToast(t("settings.platformHostBound"), "info");
        setCustomHostname(result.custom_hostname ?? "");
      } else {
        pushToast(t("settings.domainSaved"), "info");
      }
      await queryClient.invalidateQueries({ queryKey: ["org-domain"] });
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : t("errors.saveDomainFailed");
      pushToast(message, "error");
    },
  });

  const verifyDomainMutation = useMutation({
    mutationFn: () => {
      const token = domainQuery.data?.verification_token;
      if (!token) throw new ApiRequestError(t("errors.verifyTokenMissing"), 400);
      return verifyOrganizationDomain(token);
    },
    onSuccess: async () => {
      pushToast(t("settings.domainVerified"), "info");
      await queryClient.invalidateQueries({ queryKey: ["org-domain"] });
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : t("errors.verifyDomainFailed");
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
            <h2 className="text-xl font-semibold">{t("settings.title")}</h2>
            <p className="mt-1 text-sm text-slate-400">
              {user?.organization_name
                ? t("settings.subtitleOrg", { org: user.organization_name })
                : t("settings.subtitle")}
            </p>
          </div>

          {!canManage ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("settings.forbiddenTitle")}</CardTitle>
                <CardDescription>{t("settings.forbiddenBody")}</CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <>
              <TeamSection
                members={membersQuery.data}
                loading={membersQuery.isLoading}
                error={membersQuery.error}
                onRefresh={() => void membersQuery.refetch()}
              />
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
