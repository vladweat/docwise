"use client";

import { Alert } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";
import { ACCESS_ROLE_OPTIONS } from "@/lib/access-roles";
import { cn } from "@/lib/utils";

export function AccessRolesField({
  roles,
  onChange,
  showOverlapWarning,
}: {
  roles: string[];
  onChange: (roles: string[]) => void;
  showOverlapWarning: boolean;
}) {
  const { t } = useI18n();

  function toggleRole(value: string, checked: boolean) {
    onChange(checked ? [...roles, value] : roles.filter((item) => item !== value));
  }

  return (
    <fieldset>
      <Label className="mb-2">{t("documents.accessTags")}</Label>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {ACCESS_ROLE_OPTIONS.map((option) => {
          const checked = roles.includes(option.value);
          const labelKey = `accessRoles.${option.value}` as MessageKey;
          return (
            <label
              key={option.value}
              className={cn(
                "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                checked
                  ? "border-blue-500/60 bg-blue-500/10 text-slate-100"
                  : "border-slate-700 text-slate-300",
              )}
            >
              <Checkbox
                checked={checked}
                onCheckedChange={(value) => toggleRole(option.value, value === true)}
              />
              {t(labelKey)}
            </label>
          );
        })}
      </div>
      {showOverlapWarning ? <Alert variant="warning" className="mt-3">{t("documents.aclWarning")}</Alert> : null}
    </fieldset>
  );
}
