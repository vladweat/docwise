"use client";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/i18n/locale-provider";
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
  const { t } = useI18n();
  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>{t("settings.domainTitle")}</CardTitle>
          <CardDescription>{t("settings.domainDescription")}</CardDescription>
        </div>
        {domain?.custom_verified ? (
          <Badge variant="success">Verified</Badge>
        ) : domain?.custom_hostname ? (
          <Badge variant="warning">{t("settings.unverified")}</Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-slate-300">
        {loading ? <Skeleton className="h-4 w-40" /> : null}
        {error ? (
          <Alert variant="destructive">
            {error instanceof ApiRequestError ? error.message : t("errors.loadDomainFailed")}
          </Alert>
        ) : null}
        {domain ? (
          <>
            <p className="text-xs text-slate-500">
              {t("settings.platformHost")}{" "}
              {domain.platform_hostnames.map((host) => (
                <code key={host} className="mr-2 text-slate-300">
                  {host}
                </code>
              ))}
            </p>
            {!domain.entitlement ? (
              <p className="text-slate-400">{t("settings.customCnameNote")}</p>
            ) : (
              <>
                <div>
                  <Label htmlFor="custom-host">{t("settings.customCname")}</Label>
                  <Input
                    id="custom-host"
                    className="mt-1"
                    value={customHostname}
                    onChange={(event) => onHostnameChange(event.target.value)}
                    placeholder="kb.acme.example"
                    disabled={busy}
                  />
                  <p className="mt-1 text-xs text-slate-500">{t("settings.customCnameHint")}</p>
                </div>
                {domain.verification_token ? (
                  <p className="text-xs text-slate-500">
                    {t("settings.verifyToken")}{" "}
                    <code className="break-all text-slate-300">{domain.verification_token}</code>
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <Button type="button" size="sm" disabled={busy} onClick={onSave}>
                    {t("settings.saveDomain")}
                  </Button>
                  {domain.custom_hostname && !domain.custom_verified ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      disabled={busy || !domain.verification_token}
                      onClick={onVerify}
                    >
                      {t("settings.verifyDomain")}
                    </Button>
                  ) : null}
                </div>
                <p className="text-xs text-slate-500">{t("settings.unverifiedHostNote")}</p>
              </>
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
