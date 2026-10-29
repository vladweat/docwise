"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";

import {
  DEMO_ACCOUNTS,
  initialLoginVariant,
  publicDemoProfile,
  showDemoLogins,
  type DemoPersona,
  type LoginVariant,
} from "@/features/auth/demo-accounts";
import { useAuth } from "@/features/auth/auth-provider";
import { GoogleSignInButton } from "@/features/auth/google-sign-in-button";
import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type AuthMode = "login" | "register";
const DEMO_PERSONA_LABEL: Record<DemoPersona, MessageKey> = {
  employee: "auth.demoPersonaEmployee",
  hr: "auth.demoPersonaHr",
  admin: "auth.demoPersonaAdmin",
};

export function AuthPanel() {
  const { t } = useI18n();
  const { login, register, loginSso, error, clearError } = useAuth();
  const searchParams = useSearchParams();
  const publicDemo = publicDemoProfile();
  const demoLogins = showDemoLogins();
  const [mode, setMode] = useState<AuthMode>("login");
  const [loginVariant, setLoginVariant] = useState(() =>
    initialLoginVariant({
      publicDemo,
      demoLogins,
      requestedMode: searchParams.get("mode"),
    }),
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [ssoSlug, setSsoSlug] = useState(searchParams.get("sso") ?? "");
  const [ssoGroups, setSsoGroups] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const effectiveMode: AuthMode = publicDemo ? "login" : mode;
  const showLoginVariantSwitch = demoLogins;
  const openSso = Boolean(searchParams.get("sso")) && !publicDemo;
  const panelTitle =
    showLoginVariantSwitch && loginVariant === "demo"
      ? t("auth.titleDemo")
      : effectiveMode === "login"
        ? t("auth.titleLogin")
        : t("auth.titleRegister");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    try {
      if (effectiveMode === "login") {
        await login(email, password);
      } else {
        await register(email, password, organizationName, inviteToken.trim() || undefined);
      }
      setPassword("");
    } catch {
      // error handled in context
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDemoLogin(nextEmail: string, nextPassword: string) {
    clearError();
    setSubmitting(true);
    try {
      await login(nextEmail, nextPassword);
    } catch {
      // error handled in context
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSso(e: FormEvent) {
    e.preventDefault();
    clearError();
    const slug = ssoSlug.trim();
    if (!slug) return;
    setSubmitting(true);
    try {
      await loginSso(slug, {
        email,
        email_verified: true,
        groups: ssoGroups
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
      });
    } catch {
      // error handled in context
    } finally {
      setSubmitting(false);
    }
  }

  function switchMode(next: AuthMode) {
    setMode(next);
    clearError();
  }

  function switchLoginVariant(next: LoginVariant) {
    setLoginVariant(next);
    clearError();
  }

  const credentialsForm = (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <Label htmlFor="email">{t("auth.email")}</Label>
        <Input
          id="email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="user@example.com"
          autoComplete="username"
        />
      </div>

      <div>
        <Label htmlFor="password">
          {t("auth.password")}{" "}
          {effectiveMode === "register" ? t("auth.passwordMinRegister") : ""}
        </Label>
        <Input
          id="password"
          type="password"
          required
          minLength={effectiveMode === "register" ? 8 : 1}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          autoComplete={effectiveMode === "login" ? "current-password" : "new-password"}
        />
      </div>

      {effectiveMode === "register" ? (
        <>
          <div>
            <Label htmlFor="organization">{t("auth.organization")}</Label>
            <Input
              id="organization"
              type="text"
              required={!inviteToken.trim()}
              value={organizationName}
              onChange={(e) => setOrganizationName(e.target.value)}
              placeholder="Acme"
              disabled={Boolean(inviteToken.trim())}
            />
          </div>
          <div>
            <Label htmlFor="invite">{t("auth.inviteToken")}</Label>
            <Input
              id="invite"
              type="text"
              value={inviteToken}
              onChange={(e) => setInviteToken(e.target.value)}
              placeholder={t("auth.inviteOptional")}
            />
          </div>
        </>
      ) : null}

      {error ? <Alert variant="destructive">{error}</Alert> : null}

      <Button type="submit" disabled={submitting} className="w-full">
        {submitting ? "…" : effectiveMode === "login" ? t("auth.submitLogin") : t("auth.submitRegister")}
      </Button>
    </form>
  );

  const oauthSection =
    publicDemo ? null : (
      <details className="mt-5 group" open={openSso && effectiveMode === "login"}>
        <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-300 [&::-webkit-details-marker]:hidden">
          <span className="inline-flex items-center gap-1">
            <span className="transition-transform group-open:rotate-90">›</span>
            {t("auth.oauthSummary")}
          </span>
        </summary>
        <div className="mt-4 space-y-4">
          <GoogleSignInButton organizationName={effectiveMode === "register" ? organizationName : undefined} />
          {effectiveMode === "login" ? (
            <form onSubmit={handleSso} className="space-y-3">
              <p className="text-[11px] text-slate-500">{t("auth.ssoHint")}</p>
              <div>
                <Label htmlFor="sso-slug">{t("auth.ssoSlug")}</Label>
                <Input
                  id="sso-slug"
                  value={ssoSlug}
                  onChange={(e) => setSsoSlug(e.target.value)}
                  placeholder="globex-ab12cd"
                />
              </div>
              <div>
                <Label htmlFor="sso-groups">{t("auth.ssoGroups")}</Label>
                <Input
                  id="sso-groups"
                  value={ssoGroups}
                  onChange={(e) => setSsoGroups(e.target.value)}
                  placeholder="admins, hr-team"
                />
              </div>
              <Button
                type="submit"
                variant="secondary"
                disabled={submitting || !ssoSlug.trim() || !email}
                className="w-full"
              >
                {t("auth.ssoSubmit")}
              </Button>
            </form>
          ) : null}
        </div>
      </details>
    );

  const showOAuthSection = Boolean(oauthSection) && (!showLoginVariantSwitch || loginVariant === "standard");

  const demoLoginPanel = (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2">
        {DEMO_ACCOUNTS.map((account) => (
          <Button
            key={account.persona}
            type="button"
            variant="secondary"
            size="sm"
            disabled={submitting}
            className="h-9 px-2"
            onClick={() => void handleDemoLogin(account.email, account.password)}
          >
            {t(DEMO_PERSONA_LABEL[account.persona])}
          </Button>
        ))}
      </div>
      <p className="text-[11px] leading-snug text-slate-500">{t("auth.demoFlowHint")}</p>
      <p className="text-[11px] leading-snug text-slate-500">{t("auth.demoHint")}</p>
      {error ? <Alert variant="destructive">{error}</Alert> : null}
    </div>
  );

  const standardAuthPanel = (
    <>
      {publicDemo ? null : (
        <Tabs
          value={mode}
          onValueChange={(value) => switchMode(value as AuthMode)}
          className="mb-5 gap-0"
        >
          <TabsList>
            <TabsTrigger value="login">{t("auth.tabLogin")}</TabsTrigger>
            <TabsTrigger value="register">{t("auth.tabRegister")}</TabsTrigger>
          </TabsList>
        </Tabs>
      )}
      {credentialsForm}
      {showOAuthSection ? oauthSection : null}
    </>
  );

  return (
    <Panel title={panelTitle} subtitle={t("auth.subtitle")}>
      {showLoginVariantSwitch ? (
        <Tabs
          value={loginVariant}
          onValueChange={(value) => switchLoginVariant(value as LoginVariant)}
          className="mb-5 gap-0"
        >
          <TabsList>
            <TabsTrigger value="standard">{t("auth.tabEmail")}</TabsTrigger>
            <TabsTrigger value="demo">{t("auth.tabDemo")}</TabsTrigger>
          </TabsList>
        </Tabs>
      ) : null}

      {showLoginVariantSwitch && loginVariant === "demo" ? demoLoginPanel : standardAuthPanel}
    </Panel>
  );
}
