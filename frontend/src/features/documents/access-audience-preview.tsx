"use client";

import { Alert } from "@/components/ui/alert";
import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";
import { ACCESS_ROLE_OPTIONS, allowedRolesForUser, rolesOverlap } from "@/lib/access-roles";
import type { UserResponse } from "@/types/auth";

export function AccessAudiencePreview({
  roles,
  user,
}: {
  roles: string[];
  user: UserResponse | null;
}) {
  const { t } = useI18n();
  const hasSelection = roles.length > 0;
  const audience = roles.includes("all")
    ? t("accessRoles.all")
    : roles.map((role) => labelForRole(role, t)).join(", ");
  const userCanRead = user && hasSelection ? rolesOverlap(roles, allowedRolesForUser(user)) : null;

  return (
    <section className="grid gap-2 rounded-lg border border-slate-700 bg-slate-900/60 p-3" aria-live="polite">
      <h3 className="text-sm font-medium text-slate-100">{t("documents.accessPreviewTitle")}</h3>
      <p className="text-sm text-slate-300">
        {hasSelection ? audience : t("documents.accessPreviewEmpty")}
      </p>
      {userCanRead === true ? (
        <p className="rounded-lg border border-emerald-900/50 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-300">
          {t("documents.uploaderCanRead")}
        </p>
      ) : null}
      {userCanRead === false ? (
        <Alert variant="warning">{t("documents.uploaderCannotRead")}</Alert>
      ) : null}
      <p className="text-xs text-slate-400">{t("documents.noAdminReadOverride")}</p>
    </section>
  );
}

function labelForRole(role: string, translate: (key: MessageKey) => string): string {
  const roleOption = ACCESS_ROLE_OPTIONS.find((option) => option.value === role);
  if (roleOption) return translate(`accessRoles.${roleOption.value}` as MessageKey);
  const knownDepartments: Record<string, MessageKey> = {
    hr: "accessRoles.hr",
    finance: "accessRoles.finance",
    engineering: "accessRoles.engineering",
    legal: "accessRoles.legal",
    security: "accessRoles.security",
  };
  const key = knownDepartments[role];
  if (key) return translate(key);
  return role.replace(/[-_]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
