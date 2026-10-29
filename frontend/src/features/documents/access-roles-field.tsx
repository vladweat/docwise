"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { useI18n } from "@/i18n/locale-provider";
import type { MessageKey } from "@/i18n/messages";
import { ACCESS_ROLE_OPTIONS, toggleAccessRole } from "@/lib/access-roles";
import { cn } from "@/lib/utils";

export function AccessRolesField({
  roles,
  roleOptions,
  departments,
  isLoading,
  onChange,
}: {
  roles: string[];
  roleOptions: string[];
  departments: string[];
  isLoading: boolean;
  onChange: (roles: string[]) => void;
}) {
  const { t } = useI18n();
  const allSelected = roles.includes("all");
  const configuredRoles = ACCESS_ROLE_OPTIONS.filter((option) => roleOptions.includes(option.value));
  const selectedDepartments = roles.filter(
    (role) => role !== "all" && !configuredRoles.some((option) => option.value === role),
  );
  const departmentOptions = Array.from(new Set([...departments, ...selectedDepartments])).sort();

  function toggleRole(value: string, checked: boolean) {
    onChange(toggleAccessRole(roles, value, checked));
  }

  function departmentLabel(value: string): string {
    const knownLabels: Record<string, MessageKey> = {
      hr: "accessRoles.hr",
      finance: "accessRoles.finance",
      engineering: "accessRoles.engineering",
      legal: "accessRoles.legal",
      security: "accessRoles.security",
    };
    const key = knownLabels[value];
    if (key) return t(key);
    return value.replace(/[-_]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
  }

  return (
    <fieldset>
      <Label className="mb-1">{t("documents.accessTags")}</Label>
      <p className="mb-3 text-xs text-slate-400">{t("documents.accessSelectionHint")}</p>
      {isLoading ? <p className="mb-3 text-sm text-slate-400">{t("documents.loadingAccessOptions")}</p> : null}

      <div className="grid gap-4">
        <section className="grid gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {t("documents.accessEveryoneGroup")}
          </h3>
          <AccessOption
            checked={allSelected}
            disabled={isLoading}
            label={t("accessRoles.all")}
            onCheckedChange={(checked) => toggleRole("all", checked)}
          />
        </section>

        <section className="grid gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {t("documents.accessRolesGroup")}
          </h3>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {configuredRoles.map((option) => (
              <AccessOption
                key={option.value}
                checked={roles.includes(option.value)}
                disabled={isLoading || allSelected}
                label={t(`accessRoles.${option.value}` as MessageKey)}
                onCheckedChange={(checked) => toggleRole(option.value, checked)}
              />
            ))}
          </div>
        </section>

        <section className="grid gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-slate-400">
            {t("documents.accessDepartmentsGroup")}
          </h3>
          {departmentOptions.length ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {departmentOptions.map((department) => (
                <AccessOption
                  key={department}
                  checked={roles.includes(department)}
                  disabled={isLoading || allSelected}
                  label={departmentLabel(department)}
                  onCheckedChange={(checked) => toggleRole(department, checked)}
                />
              ))}
            </div>
          ) : (
            <p className="text-sm text-slate-400">{t("documents.noDepartments")}</p>
          )}
        </section>
      </div>
    </fieldset>
  );
}

function AccessOption({
  checked,
  disabled,
  label,
  onCheckedChange,
}: {
  checked: boolean;
  disabled: boolean;
  label: string;
  onCheckedChange: (checked: boolean) => void;
}) {
  return (
    <label
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer",
        checked ? "border-blue-500/60 bg-blue-500/10 text-slate-100" : "border-slate-700 text-slate-300",
      )}
    >
      <Checkbox checked={checked} disabled={disabled} onCheckedChange={(value) => onCheckedChange(value === true)} />
      {label}
    </label>
  );
}
