"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";

import { DEMO_ACCOUNTS, showDemoLogins } from "@/features/auth/demo-accounts";
import { useAuth } from "@/features/auth/auth-provider";
import { GoogleSignInButton } from "@/features/auth/google-sign-in-button";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type AuthMode = "login" | "register";

export function AuthPanel() {
  const { login, register, loginSso, error, clearError } = useAuth();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [inviteToken, setInviteToken] = useState("");
  const [ssoSlug, setSsoSlug] = useState(searchParams.get("sso") ?? "");
  const [ssoGroups, setSsoGroups] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const demoLogins = showDemoLogins();
  const openSso = Boolean(searchParams.get("sso"));

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    try {
      if (mode === "login") {
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

  return (
    <Panel title={mode === "login" ? "Вход" : "Регистрация"} subtitle="Корпоративный поиск по документам">
      <Tabs
        value={mode}
        onValueChange={(value) => switchMode(value as AuthMode)}
        className="mb-5 gap-0"
      >
        <TabsList>
          <TabsTrigger value="login">Вход</TabsTrigger>
          <TabsTrigger value="register">Регистрация</TabsTrigger>
        </TabsList>
      </Tabs>

      {mode === "login" && demoLogins ? (
        <div className="mb-5">
          <p className="mb-2 text-xs text-slate-500">Демо</p>
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
                {account.shortLabel}
              </Button>
            ))}
          </div>
          <p className="mt-2 text-[11px] leading-snug text-slate-500">
            Сотрудник и HR — один вопрос про зарплату: отказ vs цитата.
          </p>
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <Label htmlFor="email">Email</Label>
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
            Пароль {mode === "register" ? "(мин. 8 символов)" : ""}
          </Label>
          <Input
            id="password"
            type="password"
            required
            minLength={mode === "register" ? 8 : 1}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </div>

        {mode === "register" ? (
          <>
            <div>
              <Label htmlFor="organization">Организация</Label>
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
              <Label htmlFor="invite">Токен инвайта</Label>
              <Input
                id="invite"
                type="text"
                value={inviteToken}
                onChange={(e) => setInviteToken(e.target.value)}
                placeholder="необязательно"
              />
            </div>
          </>
        ) : null}

        {error ? <Alert variant="destructive">{error}</Alert> : null}

        <Button type="submit" disabled={submitting} className="w-full">
          {submitting ? "…" : mode === "login" ? "Войти" : "Зарегистрироваться"}
        </Button>
      </form>

      <details className="mt-5 group" open={openSso}>
        <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-300 [&::-webkit-details-marker]:hidden">
          <span className="inline-flex items-center gap-1">
            <span className="transition-transform group-open:rotate-90">›</span>
            Google и SSO
          </span>
        </summary>
        <div className="mt-4 space-y-4">
          <GoogleSignInButton organizationName={mode === "register" ? organizationName : undefined} />
          {mode === "login" ? (
            <form onSubmit={handleSso} className="space-y-3">
              <p className="text-[11px] text-slate-500">
                Email выше обязателен. Compose (`SSO_PROVIDER=dev`) — фикстура без Okta.
              </p>
              <div>
                <Label htmlFor="sso-slug">SSO slug</Label>
                <Input
                  id="sso-slug"
                  value={ssoSlug}
                  onChange={(e) => setSsoSlug(e.target.value)}
                  placeholder="globex-ab12cd"
                />
              </div>
              <div>
                <Label htmlFor="sso-groups">Группы IdP</Label>
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
                Войти через SSO
              </Button>
            </form>
          ) : null}
        </div>
      </details>
    </Panel>
  );
}
