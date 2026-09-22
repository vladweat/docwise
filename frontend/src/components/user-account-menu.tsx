"use client";

import { ChevronDown, LogOut } from "lucide-react";

import { LanguageSwitcher } from "@/components/language-switcher";
import { useAuth } from "@/features/auth/auth-provider";
import { useI18n } from "@/i18n/locale-provider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { formatAccessRole } from "@/lib/access-roles";
import { ApiRequestError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toast-store";

function emailInitials(email: string): string {
  const local = email.split("@")[0] ?? email;
  const parts = local.split(/[._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return local.slice(0, 2).toUpperCase();
}

export function UserAccountMenu() {
  const { t } = useI18n();
  const { user, logout, switchOrganization } = useAuth();
  const pushToast = useToastStore((state) => state.push);

  if (!user) return null;

  const orgs = user.organizations ?? [];
  const initials = emailInitials(user.email);

  return (
    <details className="relative group/menu">
      <summary
        className={cn(
          "flex cursor-pointer list-none items-center gap-1.5 rounded-lg border border-transparent px-1.5 py-1",
          "text-slate-200 hover:border-slate-800 hover:bg-slate-900/80",
          "[&::-webkit-details-marker]:hidden",
        )}
        aria-label={user.email}
      >
        <span
          className="flex size-8 shrink-0 items-center justify-center rounded-full bg-slate-800 text-xs font-semibold text-slate-100"
          aria-hidden
        >
          {initials}
        </span>
        <ChevronDown className="size-4 shrink-0 text-slate-500 transition-transform group-open/menu:rotate-180" />
      </summary>

      <div className="absolute right-0 top-[calc(100%+0.35rem)] z-[60] w-[min(calc(100vw-1.5rem),17rem)] rounded-xl border border-slate-800 bg-slate-950 py-2 shadow-xl ring-1 ring-black/20">
        <div className="px-3 pb-2">
          <p className="truncate text-sm font-medium text-slate-100">{user.email}</p>
          {orgs.length > 1 ? (
            <div className="mt-2">
              <Select
                value={user.organization_id}
                onValueChange={(organizationId) => {
                  void switchOrganization(organizationId).catch((err: unknown) => {
                    const message =
                      err instanceof ApiRequestError ? err.message : t("nav.switchOrgFailed");
                    pushToast(message, "error");
                  });
                }}
              >
                <SelectTrigger size="sm" className="h-8 w-full bg-slate-900" aria-label={t("nav.organization")}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {orgs.map((org) => (
                    <SelectItem key={org.id} value={org.id}>
                      {org.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <p className="mt-0.5 truncate text-xs text-slate-500">
              {user.organization_name}
              <span className="text-slate-600"> · </span>
              {formatAccessRole(user.role)}
            </p>
          )}
        </div>

        <Separator className="bg-slate-800" />

        <div className="flex items-center justify-between gap-2 px-3 py-2">
          <span className="text-xs text-slate-500">{t("language.label")}</span>
          <LanguageSwitcher compact className="shrink-0" />
        </div>

        <Separator className="bg-slate-800" />

        <div className="px-2 pt-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-9 w-full justify-start gap-2 text-slate-300 hover:text-slate-100"
            onClick={() => logout()}
          >
            <LogOut className="size-4" />
            {t("nav.logout")}
          </Button>
        </div>
      </div>
    </details>
  );
}
