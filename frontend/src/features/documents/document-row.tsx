"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Trash2 } from "lucide-react";

import { useAuth } from "@/features/auth/auth-provider";
import { isDocxDocument } from "@/features/documents/document-format";
import { IngestionSteps } from "@/features/documents/ingestion-steps";
import { stashPendingQuestion } from "@/features/chat/lib/pending-question";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TableCell, TableRow } from "@/components/ui/table";
import { useI18n } from "@/i18n/locale-provider";
import { accessRoleMessageKey, humanizeAccessTag, normalizeAccessRoles } from "@/lib/access-roles";
import { fetchDocumentStatus } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import { useToastStore } from "@/stores/toast-store";
import type { DocumentResponse } from "@/types/document";

const STATUS_VARIANT: Record<string, "secondary" | "success" | "warning" | "destructive"> = {
  pending: "warning",
  processing: "warning",
  ready: "success",
  failed: "destructive",
};

const IN_FLIGHT = new Set(["pending", "processing"]);

export function isDocumentInFlight(status: string): boolean {
  return IN_FLIGHT.has(status);
}

export function DocumentRow({
  doc,
  canManage,
  onPreview,
  onEditAcl,
  onAskDelete,
}: {
  doc: DocumentResponse;
  canManage: boolean;
  onPreview: (doc: DocumentResponse) => void;
  onEditAcl: (doc: DocumentResponse) => void;
  onAskDelete: (doc: DocumentResponse) => void;
}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const inFlight = isDocumentInFlight(doc.status);
  const statusQuery = useQuery({
    queryKey: ["document-status", user?.id, doc.id],
    queryFn: () => fetchDocumentStatus(doc.id),
    enabled: inFlight || doc.status === "failed",
    refetchInterval: inFlight ? 1500 : false,
  });

  const status = statusQuery.data?.status ?? doc.status;
  const stage = statusQuery.data?.stage ?? null;
  const lastError = statusQuery.data?.last_error ?? doc.last_error;
  const showSteps = isDocumentInFlight(status) || status === "failed";
  const prevStatusRef = useRef(status);

  useEffect(() => {
    const next = statusQuery.data?.status;
    if (!next || next === doc.status) return;
    if (next === "ready" || next === "failed") {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    }
  }, [doc.status, queryClient, statusQuery.data?.status]);

  useEffect(() => {
    const prev = prevStatusRef.current;
    prevStatusRef.current = status;
    if (prev === status || status !== "ready") return;
    pushToast(t("documents.readyToast", { title: doc.title }), "info", {
      label: t("documents.askAboutAction"),
      onClick: () => {
        stashPendingQuestion(t("chat.askAboutDocument", { title: doc.title }));
        router.push("/");
      },
    });
  }, [doc.title, pushToast, router, status, t]);

  return (
    <TableRow>
      <TableCell className="text-slate-100">
        {doc.title}
        <p className="mt-0.5 text-xs text-slate-500">{formatDateTime(doc.created_at)}</p>
        <Button
          type="button"
          variant="link"
          className="mt-1 h-auto p-0 text-xs text-blue-300 hover:text-blue-200"
          onClick={() => onPreview(doc)}
        >
          {isDocxDocument(doc) ? t("documents.openDocx") : t("documents.openPdf")}
        </Button>
      </TableCell>
      <TableCell className="text-slate-400">{formatBytes(doc.file_size_bytes)}</TableCell>
      <TableCell className="text-slate-400">{doc.total_pages ?? "—"}</TableCell>
      <TableCell>
        <div className="flex flex-wrap items-center gap-1">
          {normalizeAccessRoles(doc.access_roles).map((role) => (
            <Badge key={role} variant="outline">
              {accessRoleMessageKey(role) ? t(accessRoleMessageKey(role)!) : humanizeAccessTag(role)}
            </Badge>
          ))}
          {canManage ? (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              aria-label={t("documents.editAccessAria", { title: doc.title })}
              onClick={() => onEditAcl(doc)}
            >
              <Pencil className="size-3.5 text-slate-400" />
            </Button>
          ) : null}
        </div>
      </TableCell>
      <TableCell>
        <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>
        {showSteps ? (
          <IngestionSteps
            status={status}
            stage={stage ?? (status === "processing" ? "parse" : null)}
          />
        ) : null}
        {status === "failed" && lastError ? (
          <Alert variant="destructive" className="mt-2 max-w-xs px-2 py-1.5 text-xs" title={lastError}>
            {lastError}
          </Alert>
        ) : null}
      </TableCell>
      {canManage ? (
        <TableCell>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t("documents.deleteAria", { title: doc.title })}
            onClick={() => onAskDelete(doc)}
          >
            <Trash2 className="size-4 text-slate-400" />
          </Button>
        </TableCell>
      ) : null}
    </TableRow>
  );
}
