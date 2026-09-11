"use client";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiRequestError } from "@/lib/api";
import type { OrganizationDomain } from "@/types/domain";

export function DomainSection({
  domain,
  loading,
  error,
  customHostname,
  busy,
  onHostnameChange,
  onSave,
  onVerify,
}: {
  domain?: OrganizationDomain;
  loading: boolean;
  error: unknown;
  customHostname: string;
  busy: boolean;
  onHostnameChange: (value: string) => void;
  onSave: () => void;
  onVerify: () => void;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Домен</CardTitle>
          <CardDescription>Платформенный хост пинит эту org. Cookie host-only, без Domain на родителя.</CardDescription>
        </div>
        {domain?.custom_verified ? (
          <Badge variant="success">Verified</Badge>
        ) : domain?.custom_hostname ? (
          <Badge variant="warning">Не подтверждён</Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-slate-300">
        {loading ? <Skeleton className="h-4 w-40" /> : null}
        {error ? (
          <Alert variant="destructive">
            {error instanceof ApiRequestError ? error.message : "Не удалось загрузить домен"}
          </Alert>
        ) : null}
        {domain ? (
          <>
            <p className="text-xs text-slate-500">
              Платформа:{" "}
              {domain.platform_hostnames.map((host) => (
                <code key={host} className="mr-2 text-slate-300">
                  {host}
                </code>
              ))}
            </p>
            {!domain.entitlement ? (
              <p className="text-slate-400">
                Свой CNAME входит в план Enterprise. Compose: `/etc/hosts`, без Let&apos;s Encrypt.
              </p>
            ) : (
              <>
                <div>
                  <Label htmlFor="custom-host">Свой CNAME</Label>
                  <Input
                    id="custom-host"
                    className="mt-1"
                    value={customHostname}
                    onChange={(event) => onHostnameChange(event.target.value)}
                    placeholder="kb.acme.example"
                    disabled={busy}
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Свой CNAME вроде kb.acme.example. Имя на .docwise.app, которое ещё не занято другим slug, можно
                    сохранить и подтвердить.
                  </p>
                </div>
                {domain.verification_token ? (
                  <p className="text-xs text-slate-500">
                    Токен проверки (TXT/HTTP, Compose — POST verify):{" "}
                    <code className="break-all text-slate-300">{domain.verification_token}</code>
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" disabled={busy} onClick={onSave}>
                    Сохранить домен
                  </Button>
                  {domain.custom_hostname && !domain.custom_verified ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={busy || !domain.verification_token}
                      onClick={onVerify}
                    >
                      Подтвердить
                    </Button>
                  ) : null}
                </div>
                <p className="text-xs text-slate-500">
                  Неподтверждённый hostname не биндится. На хосте этой org нельзя переключиться в другую.
                </p>
              </>
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
