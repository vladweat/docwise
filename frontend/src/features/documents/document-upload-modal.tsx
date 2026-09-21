"use client";

import { useCallback, useId, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
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
import { Label } from "@/components/ui/label";
import {
  ACCESS_ROLE_OPTIONS,
  allowedRolesForUser,
  rolesOverlap,
} from "@/lib/access-roles";
import { ApiRequestError, uploadDocument } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
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
      const raw = err instanceof ApiRequestError ? err.message : "Не удалось загрузить файл";
      const message =
        err instanceof ApiRequestError ? userFacingApiMessage(err.status, err.message) : raw;
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

  const takeFile = useCallback((next: File | undefined) => {
    setError(null);
    if (!next) return;
    const name = next.name.toLowerCase();
    const isPdf = name.endsWith(".pdf") || next.type === "application/pdf";
    const isDocx =
      name.endsWith(".docx") ||
      next.type ===
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    if (!isPdf && !isDocx) {
      setError("Только PDF или DOCX");
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

  function toggleRole(value: string, checked: boolean) {
    setRoles((current) =>
      checked ? [...current, value] : current.filter((item) => item !== value),
    );
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || roles.length === 0 || mutation.isPending) return;
    mutation.mutate();
  }

  const allowed = user ? allowedRolesForUser(user) : ["all"];
  const visibleAfterUpload = rolesOverlap(roles, allowed);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) resetAndClose();
      }}
    >
      <DialogContent className="sm:max-w-lg" aria-labelledby={titleId} showCloseButton>
        <form onSubmit={onSubmit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle id={titleId}>Загрузить документ</DialogTitle>
            <DialogDescription>
              Файл попадёт в очередь: parse → chunk → embed. Теги доступа копируются на чанки.
            </DialogDescription>
          </DialogHeader>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed px-4 py-8 text-center transition-colors",
              dragging ? "border-blue-500 bg-blue-500/10" : "border-slate-700 bg-slate-950/60",
            )}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="size-8 text-slate-500" />
            <p className="mt-2 text-sm text-slate-300">
              Перетащите PDF/DOCX сюда или <span className="text-blue-400">выберите файл</span>
            </p>
            <p className="mt-1 text-xs text-slate-500">До 50 МБ</p>
            {file ? <p className="mt-2 text-sm text-slate-100">{file.name}</p> : null}
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(event) => takeFile(event.target.files?.[0])}
            />
          </div>

          <fieldset>
            <Label className="mb-2">Теги доступа</Label>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {ACCESS_ROLE_OPTIONS.map((option) => {
                const checked = roles.includes(option.value);
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
                    {option.label}
                  </label>
                );
              })}
            </div>
          </fieldset>

          {!visibleAfterUpload && roles.length > 0 ? (
            <Alert variant="warning">
              Выбранные теги не пересекаются с вашими ролями — файл не появится в этом списке (ACL).
            </Alert>
          ) : null}

          {error ? <Alert variant="destructive">{error}</Alert> : null}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={resetAndClose} disabled={mutation.isPending}>
              Отмена
            </Button>
            <Button type="submit" disabled={!file || roles.length === 0 || mutation.isPending}>
              {mutation.isPending ? "Загрузка…" : "Загрузить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
