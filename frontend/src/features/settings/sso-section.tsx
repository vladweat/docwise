"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError } from "@/lib/api";
import type { SsoConnection } from "@/types/sso";

export function SsoSection({
  enabled,
  connection,
  loading,
  error,
  idpEntityId,
  jitEnabled,
  ssoEnforced,
  attributeMapText,
  busy,
  onIdpChange,
  onJitChange,
  onEnforcedChange,
  onMapChange,
  onSave,
}: {
  enabled: boolean;
  connection?: SsoConnection;
  loading: boolean;
  error: unknown;
  idpEntityId: string;
  jitEnabled: boolean;
  ssoEnforced: boolean;
  attributeMapText: string;
  busy: boolean;
  onIdpChange: (value: string) => void;
  onJitChange: (value: boolean) => void;
  onEnforcedChange: (value: boolean) => void;
  onMapChange: (value: string) => void;
  onSave: () => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>SSO / SAML</CardTitle>
        <CardDescription>Коннектор принадлежит этой организации. Org берётся из slug, не из assertion.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-slate-300">
        {!enabled ? (
          <p className="text-slate-400">SSO входит в план Enterprise. Смена плана не открывает чужую организацию.</p>
        ) : null}
        {enabled && loading ? <Skeleton className="h-4 w-40" /> : null}
        {enabled && error ? (
          <Alert variant="destructive">
            {error instanceof ApiRequestError ? error.message : "Не удалось загрузить SSO"}
          </Alert>
        ) : null}
        {enabled && connection ? (
          <>
            <p className="text-xs text-slate-500">
              Login: <code className="text-slate-300">{connection.login_path}</code>
              <br />
              ACS: <code className="text-slate-300">{connection.acs_path}</code>
              {connection.slug ? (
                <>
                  <br />
                  Slug: <code className="text-slate-300">{connection.slug}</code>
                </>
              ) : null}
            </p>
            <div>
              <Label htmlFor="idp-entity">IdP entity ID</Label>
              <Input
                id="idp-entity"
                className="mt-1"
                value={idpEntityId}
                onChange={(event) => onIdpChange(event.target.value)}
                placeholder="https://idp.example/metadata"
                disabled={busy}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={jitEnabled} onCheckedChange={(value) => onJitChange(value === true)} disabled={busy} />
              JIT: создавать membership только в этой org
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={ssoEnforced}
                onCheckedChange={(value) => onEnforcedChange(value === true)}
                disabled={busy}
              />
              Требовать SSO (пароль и Google не входят в эту org)
            </label>
            <div>
              <Label htmlFor="attr-map">Маппинг групп IdP → role / departments</Label>
              <Textarea
                id="attr-map"
                className="mt-1 min-h-32 font-mono text-xs"
                value={attributeMapText}
                onChange={(event) => onMapChange(event.target.value)}
                disabled={busy}
                spellCheck={false}
              />
            </div>
            <Button type="button" size="sm" disabled={busy} onClick={onSave}>
              Сохранить SSO
            </Button>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
