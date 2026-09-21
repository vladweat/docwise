"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";

import { AuthGate } from "@/features/auth/auth-gate";
import { useAuth } from "@/features/auth/auth-provider";
import { DocumentsEmptyState } from "@/features/documents/documents-empty-state";
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
import { useI18n } from "@/i18n/locale-provider";
import { canManageKnowledgeBase, formatAccessRole } from "@/lib/access-roles";
import { ApiRequestError, deleteDocument, fetchDocumentStatus, fetchDocuments } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { stashPendingQuestion } from "@/features/chat/lib/pending-question";
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
  const { t } = useI18n();
  const { user } = useAuth();
  const canManage = canManageKnowledgeBase(user);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadInitialFile, setUploadInitialFile] = useState<File | null>(null);
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
              <h2 className="text-xl font-semibold">{t("documents.title")}</h2>
              <p className="mt-1 text-sm text-slate-400">
                {user?.organization_name
                  ? t("documents.subtitleOrg", { org: user.organization_name })
                  : t("documents.subtitle")}
              </p>
            </div>
            {canManage ? (
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="outline" onClick={() => setInviteOpen(true)}>
                  {t("documents.invite")}
                </Button>
                <Button type="button" onClick={() => setUploadOpen(true)}>
                  {t("documents.uploadPdf")}
                </Button>
              </div>
            ) : (
              <p className="text-xs text-slate-500">{t("documents.adminOnlyHint")}</p>
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
                : t("errors.loadDocumentsFailed")}
            </Alert>
          ) : null}
          {query.data && query.data.items.length === 0 ? (
            <DocumentsEmptyState
              canManage={canManage}
              onUploadClick={() => {
                setUploadInitialFile(null);
                setUploadOpen(true);
              }}
              onFilePicked={(file) => {
                setUploadInitialFile(file);
                setUploadOpen(true);
              }}
            />
          ) : null}
          {query.data && query.data.items.length > 0 ? (
            <div className="rounded-xl border border-slate-800">
              <Table className="min-w-[48rem]">
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("documents.colTitle")}</TableHead>
                    <TableHead>{t("documents.colSize")}</TableHead>
                    <TableHead>{t("documents.colPages")}</TableHead>
                    <TableHead>{t("documents.colAccess")}</TableHead>
                    <TableHead>{t("documents.colStatus")}</TableHead>
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
      <DocumentUploadModal
        open={uploadOpen}
        initialFile={uploadInitialFile}
        onClose={() => {
          setUploadOpen(false);
          setUploadInitialFile(null);
        }}
      />
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
  const { t } = useI18n();
  const { user } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
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
          {t("documents.openPdf")}
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

function DocumentPreviewDialog({
  document,
  onClose,
}: {
  document: DocumentResponse | null;
  onClose: () => void;
}) {
  const { t } = useI18n();
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
              {document?.content_format === "docx" || document?.title.toLowerCase().endsWith(".docx")
                ? t("documents.previewDocxHint")
                : t("documents.previewPdfHint")}
            </DialogDescription>
          </DialogHeader>
          <div className="min-h-0 min-w-0 flex-1 overflow-hidden">
            {document &&
            (document.content_format === "docx" ||
              document.title.toLowerCase().endsWith(".docx")) ? (
              <p className="p-6 text-sm text-slate-400">{t("documents.previewDocxUnsupported")}</p>
            ) : document ? (
              <DocumentPdfPreview documentId={document.id} />
            ) : null}
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
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const pushToast = useToastStore((state) => state.push);
  const mutation = useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      pushToast(t("documents.deletedToast"), "info");
      onClose();
    },
    onError: (err) => {
      const message =
        err instanceof ApiRequestError ? err.message : t("errors.deleteDocumentFailed");
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
          <AlertDialogTitle>{t("documents.deleteTitle")}</AlertDialogTitle>
          <AlertDialogDescription>
            {t("documents.deleteBody", { title: document?.title ?? "" })}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>{t("common.cancel")}</AlertDialogCancel>
          <AlertDialogAction
            className={cn(buttonVariants({ variant: "destructive" }))}
            disabled={mutation.isPending || !document}
            onClick={(event) => {
              event.preventDefault();
              if (document) mutation.mutate(document.id);
            }}
          >
            {mutation.isPending ? t("common.deleting") : t("common.delete")}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
