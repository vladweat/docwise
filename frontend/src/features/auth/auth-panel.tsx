"use client";

import { FormEvent, useState } from "react";
import { useSearchParams } from "next/navigation";

import { useAuth } from "@/features/auth/auth-provider";
import { GoogleSignInButton } from "@/features/auth/google-sign-in-button";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
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
    <Panel title="Вход" subtitle="Email и пароль, Google или SSO">
      <Tabs
        value={mode}
        onValueChange={(value) => switchMode(value as AuthMode)}
        className="mb-4 gap-0"
      >
        <TabsList>
          <TabsTrigger value="login">Вход</TabsTrigger>
          <TabsTrigger value="register">Регистрация</TabsTrigger>
        </TabsList>
      </Tabs>

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
              <Label htmlFor="invite">Токен инвайта (если есть)</Label>
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

      <div className="my-4 flex items-center gap-3">
        <Separator className="flex-1" />
        <span className="text-xs text-slate-500">или</span>
        <Separator className="flex-1" />
      </div>

      <GoogleSignInButton organizationName={mode === "register" ? organizationName : undefined} />

      {mode === "login" ? (
        <form onSubmit={handleSso} className="mt-4 space-y-3 border-t border-slate-800 pt-4">
          <p className="text-xs text-slate-500">
            SSO по slug организации. Compose (`SSO_PROVIDER=dev`) принимает фикстуру без Okta.
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
            <Label htmlFor="sso-groups">Группы IdP (через запятую)</Label>
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
    </Panel>
  );
}
