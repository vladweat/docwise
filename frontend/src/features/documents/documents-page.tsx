"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";

import { AuthGate } from "@/features/auth/auth-gate";
import { useAuth } from "@/features/auth/auth-provider";
import { DocumentUploadModal } from "@/features/documents/document-upload-modal";
import { InviteMemberModal } from "@/features/documents/invite-member-modal";
import { IngestionSteps } from "@/features/documents/ingestion-steps";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { FadeIn } from "@/components/ui/fade-in";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { canManageKnowledgeBase, formatAccessRole } from "@/lib/access-roles";
import { ApiRequestError, deleteDocument, fetchDocumentStatus, fetchDocuments } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useToastStore } from "@/stores/toast-store";
import type { DocumentResponse } from "@/types/document";
import { DocumentPdfPreview } from "@/features/documents/document-pdf-preview";

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
  const [previewDocument, setPreviewDocument] = useState<DocumentResponse | null>(null);
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
        <FadeIn className="mx-auto max-w-5xl space-y-4">
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
          {query.isLoading ? (
            <div className="space-y-2 rounded-xl border border-slate-800 p-3">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-2/3" />
            </div>
          ) : null}
          {query.error ? (
            <Alert variant="destructive">
              {query.error instanceof ApiRequestError
                ? query.error.message
                : "Не удалось загрузить документы"}
            </Alert>
          ) : null}
          {query.data && query.data.items.length === 0 ? (
            <Alert>
              Пока нет документов, которые вам видно. Чужие теги и чужая организация сюда не
              попадают. Если это локальный стенд: `make demo`, затем обновите список.
            </Alert>
          ) : null}
          {query.data && query.data.items.length > 0 ? (
            <div className="rounded-xl border border-slate-800">
              <Table className="min-w-[48rem]">
                <TableHeader>
                  <TableRow>
                    <TableHead>Название</TableHead>
                    <TableHead>Размер</TableHead>
                    <TableHead>Страницы</TableHead>
                    <TableHead>Доступ</TableHead>
                    <TableHead>Статус</TableHead>
                    {canManage ? <TableHead> </TableHead> : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {query.data.items.map((doc) => (
                    <DocumentRow
                      key={doc.id}
                      doc={doc}
                      canManage={canManage}
                      onPreview={setPreviewDocument}
                      onAskDelete={setPendingDelete}
                    />
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : null}
        </FadeIn>
      </main>
      <DocumentUploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
      <InviteMemberModal open={inviteOpen} onClose={() => setInviteOpen(false)} />
      <DocumentPreviewDialog document={previewDocument} onClose={() => setPreviewDocument(null)} />
      <DeleteConfirmDialog document={pendingDelete} onClose={() => setPendingDelete(null)} />
    </AuthGate>
  );
}

function DocumentRow({
  doc,
  canManage,
  onPreview,
  onAskDelete,
}: {
  doc: DocumentResponse;
  canManage: boolean;
  onPreview: (doc: DocumentResponse) => void;
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
          Открыть PDF
        </Button>
      </TableCell>
      <TableCell className="text-slate-400">{formatBytes(doc.file_size_bytes)}</TableCell>
      <TableCell className="text-slate-400">{doc.total_pages ?? "—"}</TableCell>
      <TableCell>
        <div className="flex flex-wrap gap-1">
          {doc.access_roles.map((role) => (
            <Badge key={role} variant="outline">
              {formatAccessRole(role)}
            </Badge>
          ))}
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
            aria-label={`Удалить ${doc.title}`}
            onClick={() => onAskDelete(doc)}
          >
            <Trash2 className="size-4 text-slate-400" />
          </Button>
        </TableCell>
      ) : null}
    </TableRow>
  );
}

function DocumentPreviewDialog({
  document,
  onClose,
}: {
  document: DocumentResponse | null;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={document !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="flex h-[min(90dvh,52rem)] max-h-[90dvh] w-[min(96vw,72rem)] max-w-[min(96vw,72rem)] min-w-0 flex-col overflow-hidden p-0" showCloseButton>
        <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden">
          <DialogHeader className="border-b border-slate-800 px-4 py-3 pr-12">
            <DialogTitle>{document?.title}</DialogTitle>
            <DialogDescription>
              Просмотр PDF: листайте страницы и меняйте масштаб в панели ниже заголовка.
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
            {document ? <DocumentPdfPreview documentId={document.id} /> : null}
          </div>
        </div>
      </DialogContent>
    </Dialog>
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

  return (
    <AlertDialog
      open={document !== null}
      onOpenChange={(open) => {
        if (!open && !mutation.isPending) onClose();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить документ?</AlertDialogTitle>
          <AlertDialogDescription>
            «{document?.title}» будет удалён вместе с чанками и файлом в хранилище. Это нельзя отменить.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>Отмена</AlertDialogCancel>
          <AlertDialogAction
            className={cn(buttonVariants({ variant: "destructive" }))}
            disabled={mutation.isPending || !document}
            onClick={(event) => {
              event.preventDefault();
              if (document) mutation.mutate(document.id);
            }}
          >
            {mutation.isPending ? "Удаление…" : "Удалить"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
