"use client";

import { DocumentPdfPreview } from "@/features/documents/document-pdf-preview";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/i18n/locale-provider";
import type { DocumentResponse } from "@/types/document";

export function DocumentPreviewDialog({
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
