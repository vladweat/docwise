"use client";

import { FormEvent, useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ACCESS_ROLE_OPTIONS } from "@/lib/access-roles";
import { ApiRequestError, createOrganizationInvite } from "@/lib/api";
import { useToastStore } from "@/stores/toast-store";

const INVITE_ROLES = [
  { value: "employee", label: "Employee" },
  { value: "manager", label: "Manager" },
  { value: "admin", label: "Admin" },
] as const;

const DEPARTMENT_OPTIONS = ACCESS_ROLE_OPTIONS.filter(
  (item) => !["all", "admin", "manager", "employee"].includes(item.value),
);

export function InviteMemberModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const titleId = useId();
  const pushToast = useToastStore((state) => state.push);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("employee");
  const [departments, setDepartments] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await createOrganizationInvite({
        email,
        role,
        departments,
      });
      if (result.status === "added") {
        pushToast("Пользователь добавлен в организацию", "info");
        onClose();
      } else {
        setToken(result.invite_token);
        pushToast("Инвайт создан. Передайте токен новому сотруднику.", "info");
      }
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось пригласить";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" role="presentation">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-950 p-5 shadow-xl"
      >
        <h2 id={titleId} className="text-lg font-semibold">
          Пригласить в организацию
        </h2>
        <p className="mt-1 text-sm text-slate-400">
          Существующий email получит членство сразу. Новый пользователь регистрируется с токеном инвайта.
        </p>
        {token ? (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-slate-300">Токен инвайта (один раз):</p>
            <code className="block break-all rounded-md bg-slate-900 p-2 text-xs text-slate-200">{token}</code>
            <Button type="button" className="w-full" onClick={onClose}>
              Готово
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-4 space-y-3">
            <div>
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div>
              <Label htmlFor="invite-role">Роль</Label>
              <select
                id="invite-role"
                className="mt-1 w-full rounded-md border border-slate-700 bg-slate-900 px-2 py-2 text-sm"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                {INVITE_ROLES.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <fieldset>
              <legend className="text-sm font-medium">Отделы</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {DEPARTMENT_OPTIONS.map((item) => {
                  const checked = departments.includes(item.value);
                  return (
                    <label key={item.value} className="flex items-center gap-1 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          setDepartments((current) =>
                            checked
                              ? current.filter((value) => value !== item.value)
                              : [...current, item.value],
                          );
                        }}
                      />
                      {item.label}
                    </label>
                  );
                })}
              </div>
            </fieldset>
            {error ? <p className="text-sm text-red-400">{error}</p> : null}
            <div className="flex gap-2">
              <Button type="button" variant="secondary" className="flex-1" onClick={onClose}>
                Отмена
              </Button>
              <Button type="submit" className="flex-1" disabled={submitting}>
                {submitting ? "…" : "Пригласить"}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
