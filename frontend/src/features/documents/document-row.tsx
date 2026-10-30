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
    <TableRow className="mb-3 grid grid-cols-2 gap-x-4 gap-y-3 rounded-xl border border-slate-800 bg-slate-950/40 p-3 lg:mb-0 lg:table-row lg:gap-0 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0">
      <TableCell className="col-span-2 min-w-0 p-0 text-slate-100 lg:col-span-1 lg:px-3 lg:py-2">
        <div className="flex min-w-0 flex-wrap items-center gap-x-2 lg:block">
          <p className="min-w-0 flex-1 truncate lg:whitespace-normal lg:break-words">{doc.title}</p>
          <p className="shrink-0 whitespace-nowrap text-[10px] text-slate-500 lg:mt-0.5 lg:text-xs">
            {formatDateTime(doc.created_at)}
          </p>
          <Button
            type="button"
            variant="link"
            className="h-7 shrink-0 whitespace-nowrap px-0 text-xs text-blue-300 hover:text-blue-200 lg:mt-1 lg:block lg:h-auto"
            onClick={() => onPreview(doc)}
          >
            {isDocxDocument(doc) ? t("documents.openDocx") : t("documents.openPdf")}
          </Button>
        </div>
        <details className="mt-1 lg:hidden">
          <summary className="w-fit cursor-pointer py-1 text-xs text-slate-400">
            {t("documents.moreDetails")}
          </summary>
          <div className="grid grid-cols-2 gap-3 pt-1 text-xs">
            <div>
              <span className="block text-[10px] uppercase tracking-wide text-slate-500">
                {t("documents.colSize")}
              </span>
              <span className="text-slate-300">{formatBytes(doc.file_size_bytes)}</span>
            </div>
            <div>
              <span className="block text-[10px] uppercase tracking-wide text-slate-500">
                {t("documents.colPages")}
              </span>
              <span className="text-slate-300">{doc.total_pages ?? "—"}</span>
            </div>
          </div>
        </details>
      </TableCell>
      <TableCell className="hidden text-slate-400 lg:table-cell">
        {formatBytes(doc.file_size_bytes)}
      </TableCell>
      <TableCell className="hidden text-slate-400 lg:table-cell">
        {doc.total_pages ?? "—"}
      </TableCell>
      <TableCell className="col-span-2 min-w-0 p-0 lg:col-span-1 lg:px-3 lg:py-2">
        <span className="mr-1 inline text-[10px] font-medium uppercase tracking-wide text-slate-500 lg:hidden">
          {t("documents.colAccess")}
        </span>
        <div className="inline-flex flex-wrap items-center gap-1">
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
              className="size-11 lg:size-8"
              aria-label={t("documents.editAccessAria", { title: doc.title })}
              onClick={() => onEditAcl(doc)}
            >
              <Pencil className="size-3.5 text-slate-400" />
            </Button>
          ) : null}
        </div>
      </TableCell>
      <TableCell className={`${canManage ? "col-span-1" : "col-span-2"} min-w-0 p-0 lg:col-span-1 lg:px-3 lg:py-2`}>
        <span className="mr-1 inline text-[10px] font-medium uppercase tracking-wide text-slate-500 lg:hidden">
          {t("documents.colStatus")}
        </span>
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
        <TableCell className="flex items-center justify-end p-0 lg:table-cell lg:px-3 lg:py-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-11 lg:size-8"
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
