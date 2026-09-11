"use client";

import { FormEvent, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ACCESS_ROLE_OPTIONS } from "@/lib/access-roles";
import { ApiRequestError, createOrganizationInvite } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
import { useToastStore } from "@/stores/toast-store";

const INVITE_ROLES = [
  { value: "employee", label: "Employee" },
  { value: "manager", label: "Manager (knowledge base)" },
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
  const pushToast = useToastStore((state) => state.push);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("employee");
  const [departments, setDepartments] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);

  function resetAndClose() {
    setEmail("");
    setRole("employee");
    setDepartments([]);
    setSubmitting(false);
    setError(null);
    setToken(null);
    onClose();
  }

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
        resetAndClose();
      } else {
        setToken(result.invite_token);
        pushToast("Инвайт создан. Передайте токен новому сотруднику.", "info");
      }
    } catch (err) {
      const message =
        err instanceof ApiRequestError
          ? userFacingApiMessage(err.status, err.message)
          : "Не удалось пригласить";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) resetAndClose();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Пригласить в организацию</DialogTitle>
          <DialogDescription>
            Существующий email получит членство сразу. Новый пользователь регистрируется с токеном инвайта.
          </DialogDescription>
        </DialogHeader>
        {token ? (
          <div className="space-y-3">
            <p className="text-sm text-slate-300">Токен инвайта (один раз):</p>
            <code className="block break-all rounded-md bg-slate-950 p-2 text-xs text-slate-200">{token}</code>
            <Button type="button" className="w-full" onClick={resetAndClose}>
              Готово
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="grid gap-3">
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
              <Select value={role} onValueChange={setRole}>
                <SelectTrigger id="invite-role" className="mt-1">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INVITE_ROLES.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <fieldset>
              <legend className="text-sm font-medium">Отделы</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {DEPARTMENT_OPTIONS.map((item) => {
                  const checked = departments.includes(item.value);
                  return (
                    <label key={item.value} className="flex items-center gap-1.5 text-xs text-slate-300">
                      <Checkbox
                        checked={checked}
                        onCheckedChange={(value) => {
                          setDepartments((current) =>
                            value === true
                              ? [...current, item.value]
                              : current.filter((entry) => entry !== item.value),
                          );
                        }}
                      />
                      {item.label}
                    </label>
                  );
                })}
              </div>
            </fieldset>
            {error ? <Alert variant="destructive">{error}</Alert> : null}
            <DialogFooter>
              <Button type="button" variant="secondary" className="flex-1" onClick={resetAndClose}>
                Отмена
              </Button>
              <Button type="submit" className="flex-1" disabled={submitting}>
                {submitting ? "…" : "Пригласить"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
