"use client";

import { useCallback, useRef, useState, type DragEvent } from "react";
import { Upload } from "lucide-react";

import { showDemoLogins } from "@/features/auth/demo-accounts";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { cn } from "@/lib/utils";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export function DocumentsEmptyState({
  canManage,
  onUploadClick,
  onFilePicked,
}: {
  canManage: boolean;
  onUploadClick: () => void;
  onFilePicked: (file: File) => void;
}) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const showLocalBanner = showDemoLogins();

  const takeFile = useCallback(
    (next: File | undefined) => {
      setError(null);
      if (!next) return;
      const name = next.name.toLowerCase();
      const isPdf = name.endsWith(".pdf") || next.type === "application/pdf";
      const isDocx =
        name.endsWith(".docx") ||
        next.type === "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      if (!isPdf && !isDocx) {
        setError(t("documents.onlyPdfDocx"));
        return;
      }
      if (next.size > MAX_UPLOAD_BYTES) {
        setError(t("documents.fileTooLarge"));
        return;
      }
      onFilePicked(next);
    },
    [onFilePicked, t],
  );

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!canManage) return;
    takeFile(event.dataTransfer.files[0]);
  }

  if (!canManage) {
    return (
      <div className="space-y-3">
        {showLocalBanner ? (
          <Alert variant="default">{t("documents.localDemoBanner")}</Alert>
        ) : null}
        <Alert>{t("documents.emptyEmployee")}</Alert>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {showLocalBanner ? (
        <Alert variant="default">{t("documents.localDemoBanner")}</Alert>
      ) : null}
      <div
        onDragOver={(event) => {
          if (!canManage) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center justify-center rounded-xl border border-dashed px-4 py-12 text-center transition-colors",
          dragging ? "border-blue-500 bg-blue-500/10" : "border-slate-700 bg-slate-950/40",
        )}
      >
        <Upload className="size-10 text-slate-500" aria-hidden />
        <p className="mt-3 max-w-sm text-sm text-slate-300">{t("documents.emptyAdmin")}</p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Button type="button" onClick={onUploadClick}>
            {t("documents.uploadPdf")}
          </Button>
          <Button type="button" variant="outline" onClick={() => inputRef.current?.click()}>
            {t("documents.uploadPick")}
          </Button>
        </div>
        <p className="mt-2 text-xs text-slate-500">{t("documents.uploadMaxSize")}</p>
        {error ? (
          <p className="mt-3 text-sm text-red-400" role="alert">{error}</p>
        ) : null}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf,.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(event) => takeFile(event.target.files?.[0])}
        />
      </div>
    </div>
  );
}
