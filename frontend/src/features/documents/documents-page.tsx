"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { AuthGate } from "@/features/auth/auth-gate";
import { useAuth } from "@/features/auth/auth-provider";
import { DocumentsEmptyState } from "@/features/documents/documents-empty-state";
import { DocumentUploadModal } from "@/features/documents/document-upload-modal";
import { DocumentDeleteDialog } from "@/features/documents/document-delete-dialog";
import { DocumentAclDialog } from "@/features/documents/document-acl-dialog";
import { DocumentPreviewDialog } from "@/features/documents/document-preview-dialog";
import { DocumentRow, isDocumentInFlight } from "@/features/documents/document-row";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FadeIn } from "@/components/ui/fade-in";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useI18n } from "@/i18n/locale-provider";
import { canManageKnowledgeBase } from "@/lib/access-roles";
import { ApiRequestError, fetchDocuments } from "@/lib/api";
import type { DocumentResponse } from "@/types/document";

export function DocumentsPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const canManage = canManageKnowledgeBase(user);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadInitialFile, setUploadInitialFile] = useState<File | null>(null);
  const [previewDocument, setPreviewDocument] = useState<DocumentResponse | null>(null);
  const [pendingDelete, setPendingDelete] = useState<DocumentResponse | null>(null);
  const [aclDocument, setAclDocument] = useState<DocumentResponse | null>(null);

  const query = useQuery({
    queryKey: ["documents", user?.id, user?.organization_id],
    queryFn: () => fetchDocuments(50, 0),
    enabled: Boolean(user),
    refetchInterval: (current) => {
      const items = current.state.data?.items ?? [];
      return items.some((doc) => isDocumentInFlight(doc.status)) ? 2000 : false;
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
              <Button type="button" onClick={() => setUploadOpen(true)}>
                {t("documents.uploadPdf")}
              </Button>
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
                      onEditAcl={setAclDocument}
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
      <DocumentPreviewDialog document={previewDocument} onClose={() => setPreviewDocument(null)} />
      <DocumentAclDialog document={aclDocument} onClose={() => setAclDocument(null)} />
      <DocumentDeleteDialog document={pendingDelete} onClose={() => setPendingDelete(null)} />
    </AuthGate>
  );
}
