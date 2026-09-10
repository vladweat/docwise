"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";

import { AuthGate } from "@/components/auth-gate";
import { useAuth } from "@/components/auth-provider";
import { DocumentUploadModal } from "@/components/document-upload-modal";
import { InviteMemberModal } from "@/components/invite-member-modal";
import { IngestionSteps } from "@/components/ingestion-steps";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { canManageKnowledgeBase, formatAccessRole } from "@/lib/access-roles";
import { ApiRequestError, deleteDocument, fetchDocumentStatus, fetchDocuments } from "@/lib/api";
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

function isInFlight(status: string): boolean {
  return IN_FLIGHT.has(status);
}

export function DocumentsPage() {
  const { user } = useAuth();
  const canManage = canManageKnowledgeBase(user);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<DocumentResponse | null>(null);

  const query = useQuery({
    queryKey: ["documents", user?.id, user?.organization_id],
    queryFn: () => fetchDocuments(50, 0),
    enabled: Boolean(user),
    refetchInterval: (current) => {
      const items = current.state.data?.items ?? [];
      return items.some((doc) => isInFlight(doc.status)) ? 2000 : false;
    },
  });

  return (
    <AuthGate>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">База знаний</h2>
              <p className="mt-1 text-sm text-slate-400">
                {user?.organization_name
                  ? `Организация «${user.organization_name}». Список только документов, которые пересекаются с вашими ролями.`
                  : "Список только документов, которые пересекаются с вашими ролями. Чужие ACL сюда не попадают."}
              </p>
            </div>
            {canManage ? (
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => setInviteOpen(true)}>
                  Пригласить
                </Button>
                <Button type="button" onClick={() => setUploadOpen(true)}>
                  Загрузить PDF
                </Button>
              </div>
            ) : (
              <p className="text-xs text-slate-500">Загрузка и удаление — только admin.</p>
            )}
          </div>
          {query.isLoading ? <p className="text-sm text-slate-400">Загрузка…</p> : null}
          {query.error ? (
            <p className="text-sm text-red-400">
              {query.error instanceof ApiRequestError
                ? query.error.message
                : "Не удалось загрузить документы"}
            </p>
          ) : null}
          {query.data && query.data.items.length === 0 ? (
            <p className="text-sm text-slate-400">Пока нет документов, которые вам видно.</p>
          ) : null}
          {query.data && query.data.items.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full min-w-[48rem] text-left text-sm">
                <thead className="border-b border-slate-800 bg-slate-900/70 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">Название</th>
                    <th className="px-3 py-2 font-medium">Размер</th>
                    <th className="px-3 py-2 font-medium">Страницы</th>
                    <th className="px-3 py-2 font-medium">Доступ</th>
                    <th className="px-3 py-2 font-medium">Статус</th>
                    {canManage ? <th className="px-3 py-2 font-medium"> </th> : null}
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      doc={doc}
                      canManage={canManage}
                      onAskDelete={setPendingDelete}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </main>
      <DocumentUploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
      <InviteMemberModal open={inviteOpen} onClose={() => setInviteOpen(false)} />
      <DeleteConfirmDialog document={pendingDelete} onClose={() => setPendingDelete(null)} />
    </AuthGate>
  );
}

function DocumentRow({
  doc,
  canManage,
  onAskDelete,
}: {
  doc: DocumentResponse;
  canManage: boolean;
  onAskDelete: (doc: DocumentResponse) => void;
}) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const inFlight = isInFlight(doc.status);
  const statusQuery = useQuery({
    queryKey: ["document-status", user?.id, doc.id],
    queryFn: () => fetchDocumentStatus(doc.id),
    enabled: inFlight || doc.status === "failed",
    refetchInterval: inFlight ? 1500 : false,
  });

  const status = statusQuery.data?.status ?? doc.status;
  const stage = statusQuery.data?.stage ?? null;
  const lastError = statusQuery.data?.last_error ?? doc.last_error;
  const showSteps = isInFlight(status) || status === "failed";

  useEffect(() => {
    const next = statusQuery.data?.status;
    if (!next || next === doc.status) return;
    if (next === "ready" || next === "failed") {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    }
  }, [doc.status, queryClient, statusQuery.data?.status]);

  return (
    <tr className="border-b border-slate-800/80 align-top last:border-0">
      <td className="px-3 py-2 text-slate-100">
        {doc.title}
        <p className="mt-0.5 text-xs text-slate-500">{formatDateTime(doc.created_at)}</p>
      </td>
      <td className="px-3 py-2 text-slate-400">{formatBytes(doc.file_size_bytes)}</td>
      <td className="px-3 py-2 text-slate-400">{doc.total_pages ?? "—"}</td>
      <td className="px-3 py-2">
        <div className="flex flex-wrap gap-1">
          {doc.access_roles.map((role) => (
            <Badge key={role} variant="outline">
              {formatAccessRole(role)}
            </Badge>
          ))}
        </div>
      </td>
      <td className="px-3 py-2">
        <Badge variant={STATUS_VARIANT[status] ?? "secondary"}>{status}</Badge>
        {showSteps ? (
          <IngestionSteps
            status={status}
            stage={stage ?? (status === "processing" ? "parse" : null)}
          />
        ) : null}
        {status === "failed" && lastError ? (
          <p className="mt-1 max-w-xs text-xs text-red-400" title={lastError}>
            {lastError}
          </p>
        ) : null}
      </td>
      {canManage ? (
        <td className="px-3 py-2">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={`Удалить ${doc.title}`}
            onClick={() => onAskDelete(doc)}
          >
            <Trash2 className="size-4 text-slate-400" />
          </Button>
        </td>
      ) : null}
    </tr>
  );
}

function DeleteConfirmDialog({
  document,
  onClose,
}: {
  document: DocumentResponse | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const mutation = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      pushToast("Документ удалён", "info");
      onClose();
    },
    onError: (err) => {
      const message = err instanceof ApiRequestError ? err.message : "Не удалось удалить документ";
      pushToast(message, "error");
    },
  });

  useEffect(() => {
    if (!document) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [document, onClose]);

  if (!document) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/70 p-4 sm:items-center">
      <button type="button" className="absolute inset-0 cursor-default" aria-label="Закрыть" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-doc-title"
        className="relative z-10 w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-5 shadow-xl"
      >
        <h3 id="delete-doc-title" className="text-lg font-semibold text-slate-100">
          Удалить документ?
        </h3>
        <p className="mt-2 text-sm text-slate-400">
          «{document.title}» будет удалён вместе с чанками и файлом в хранилище. Это нельзя отменить.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={mutation.isPending}>
            Отмена
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(document.id)}
          >
            {mutation.isPending ? "Удаление…" : "Удалить"}
          </Button>
        </div>
      </div>
    </div>
  );
}
