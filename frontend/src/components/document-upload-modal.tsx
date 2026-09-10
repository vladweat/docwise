"use client";

import { useCallback, useEffect, useId, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  ACCESS_ROLE_OPTIONS,
  allowedRolesForUser,
  rolesOverlap,
} from "@/lib/access-roles";
import { ApiRequestError, uploadDocument } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toast-store";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export function DocumentUploadModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const [file, setFile] = useState<File | null>(null);
  const [roles, setRoles] = useState<string[]>(["all"]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Выберите PDF");
      return uploadDocument(file, roles);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      pushToast("Файл поставлен в очередь обработки", "info");
      resetAndClose();
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось загрузить файл";
      setError(message);
      pushToast(message, "error");
    },
  });

  function resetAndClose() {
    setFile(null);
    setRoles(["all"]);
    setError(null);
    setDragging(false);
    mutation.reset();
    onClose();
  }

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") resetAndClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const takeFile = useCallback((next: File | undefined) => {
    setError(null);
    if (!next) return;
    const name = next.name.toLowerCase();
    if (!name.endsWith(".pdf") && next.type !== "application/pdf") {
      setError("Только PDF");
      return;
    }
    if (next.size > MAX_UPLOAD_BYTES) {
      setError("Файл больше 50 МБ");
      return;
    }
    setFile(next);
  }, []);

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    takeFile(event.dataTransfer.files[0]);
  }

  function toggleRole(value: string) {
    setRoles((current) =>
      current.includes(value) ? current.filter((item) => item !== value) : [...current, value],
    );
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || roles.length === 0 || mutation.isPending) return;
    mutation.mutate();
  }

  if (!open) return null;

  const allowed = user ? allowedRolesForUser(user) : ["all"];
  const visibleAfterUpload = rolesOverlap(roles, allowed);

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/70 p-4 sm:items-center">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Закрыть" onClick={resetAndClose} />
      <form
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onSubmit={onSubmit}
        className="relative z-10 w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-xl"
      >
        <h3 id={titleId} className="text-lg font-semibold text-slate-100">
          Загрузить PDF
        </h3>
        <p className="mt-1 text-sm text-slate-400">
          Файл попадёт в очередь: parse → chunk → embed. Теги доступа копируются на чанки.
        </p>

        <div
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-8 text-center transition-colors",
            dragging ? "border-blue-500 bg-blue-500/10" : "border-slate-700 bg-slate-950/60",
          )}
          onClick={() => inputRef.current?.click()}
        >
          <Upload className="size-8 text-slate-500" />
          <p className="mt-2 text-sm text-slate-300">
            Перетащите PDF сюда или <span className="text-blue-400">выберите файл</span>
          </p>
          <p className="mt-1 text-xs text-slate-500">До 50 МБ</p>
          {file ? <p className="mt-2 text-sm text-slate-100">{file.name}</p> : null}
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(event) => takeFile(event.target.files?.[0])}
          />
        </div>

        <fieldset className="mt-4">
          <Label className="mb-2">Теги доступа</Label>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {ACCESS_ROLE_OPTIONS.map((option) => {
              const checked = roles.includes(option.value);
              return (
                <label
                  key={option.value}
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    checked ? "border-blue-500/60 bg-blue-500/10 text-slate-100" : "border-slate-700 text-slate-300",
                  )}
                >
                  <input
                    type="checkbox"
                    className="accent-blue-500"
                    checked={checked}
                    onChange={() => toggleRole(option.value)}
                  />
                  {option.label}
                </label>
              );
            })}
          </div>
        </fieldset>

        {!visibleAfterUpload && roles.length > 0 ? (
          <p className="mt-3 text-xs text-amber-300">
            Выбранные теги не пересекаются с вашими ролями — файл не появится в этом списке (ACL).
          </p>
        ) : null}

        {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}

        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={resetAndClose} disabled={mutation.isPending}>
            Отмена
          </Button>
          <Button type="submit" disabled={!file || roles.length === 0 || mutation.isPending}>
            {mutation.isPending ? "Загрузка…" : "Загрузить"}
          </Button>
        </div>
      </form>
    </div>
  );
}
