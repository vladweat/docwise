"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type DragEvent,
  type FormEvent,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AccessRolesField } from "@/features/documents/access-roles-field";
import { AccessAudiencePreview } from "@/features/documents/access-audience-preview";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/i18n/locale-provider";
import { canManageKnowledgeBase } from "@/lib/access-roles";
import { ApiRequestError, fetchDocumentAccessOptions, uploadDocument } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toast-store";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export function DocumentUploadModal({
  open,
  onClose,
  initialFile = null,
}: {
  open: boolean;
  onClose: () => void;
  initialFile?: File | null;
}) {
  const titleId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const { user } = useAuth();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const accessOptionsQuery = useQuery({
    queryKey: ["document-access-options", user?.organization_id],
    queryFn: fetchDocumentAccessOptions,
    enabled: open && canManageKnowledgeBase(user),
  });
  const [file, setFile] = useState<File | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (!file) throw new Error(t("errors.selectFile"));
      return uploadDocument(file, roles);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      pushToast(t("documents.queuedToast"), "info");
      resetAndClose();
    },
    onError: (err) => {
      const raw = err instanceof ApiRequestError ? err.message : t("errors.uploadFailed");
      const message =
        err instanceof ApiRequestError ? userFacingApiMessage(err.status, err.message) : raw;
      setError(message);
      pushToast(message, "error");
    },
  });

  function resetAndClose() {
    setFile(null);
    setRoles([]);
    setError(null);
    setDragging(false);
    mutation.reset();
    onClose();
  }

  const takeFile = useCallback(
    (next: File | undefined) => {
      setError(null);
      if (!next) return;
      const name = next.name.toLowerCase();
      const isPdf = name.endsWith(".pdf") || next.type === "application/pdf";
      const isDocx =
        name.endsWith(".docx") ||
        next.type ===
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      if (!isPdf && !isDocx) {
        setError(t("documents.onlyPdfDocx"));
        return;
      }
      if (next.size > MAX_UPLOAD_BYTES) {
        setError(t("documents.fileTooLarge"));
        return;
      }
      setFile(next);
    },
    [t],
  );

  useEffect(() => {
    if (open && initialFile) takeFile(initialFile);
  }, [open, initialFile, takeFile]);

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    takeFile(event.dataTransfer.files[0]);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || roles.length === 0 || mutation.isPending) return;
    mutation.mutate();
  }

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
            <DialogTitle id={titleId}>{t("documents.uploadTitle")}</DialogTitle>
            <DialogDescription>{t("documents.uploadDescription")}</DialogDescription>
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
              {t("documents.uploadDrop")}
              <span className="text-blue-400">{t("documents.uploadPick")}</span>
            </p>
            <p className="mt-1 text-xs text-slate-500">{t("documents.uploadMaxSize")}</p>
            {file ? <p className="mt-2 text-sm text-slate-100">{file.name}</p> : null}
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              className="hidden"
              onChange={(event) => takeFile(event.target.files?.[0])}
            />
          </div>

          <AccessRolesField
            roles={roles}
            roleOptions={accessOptionsQuery.data?.roles ?? []}
            departments={accessOptionsQuery.data?.departments ?? []}
            isLoading={accessOptionsQuery.isLoading}
            onChange={setRoles}
          />
          {accessOptionsQuery.isError ? (
            <Alert variant="destructive">
              {accessOptionsQuery.error instanceof ApiRequestError
                ? accessOptionsQuery.error.message
                : t("errors.loadAccessOptionsFailed")}
            </Alert>
          ) : null}
          <AccessAudiencePreview roles={roles} user={user} />

          {error ? <Alert variant="destructive">{error}</Alert> : null}

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={resetAndClose} disabled={mutation.isPending}>
              {t("common.cancel")}
            </Button>
            <Button
              type="submit"
              disabled={
                !file ||
                roles.length === 0 ||
                accessOptionsQuery.isLoading ||
                accessOptionsQuery.isError ||
                mutation.isPending
              }
            >
              {mutation.isPending ? t("common.uploading") : t("common.upload")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
