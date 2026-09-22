"use client";

import { Download, LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { ApiRequestError, fetchDocumentRaw } from "@/lib/api";
import type { DocumentResponse } from "@/types/document";

export function DocumentDocxPreview({ document }: { document: DocumentResponse }) {
  const { t } = useI18n();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  const snippet = document.preview_snippet?.trim() ?? "";

  useEffect(() => {
    setError(null);
    let objectUrl: string | null = null;
    setLoading(true);
    void fetchDocumentRaw(document.id)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setDownloadUrl(objectUrl);
      })
      .catch((err) => {
        const message = err instanceof ApiRequestError ? err.message : t("errors.loadDocxFailed");
        setError(message);
      })
      .finally(() => setLoading(false));

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [document.id, t]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-4">
      <p className="text-xs text-slate-500">{t("documents.previewDocxSnippetHint")}</p>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <LoaderCircle className="size-4 animate-spin" />
          {t("gate.loading")}
        </div>
      ) : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {downloadUrl ? (
        <Button type="button" variant="secondary" size="sm" className="w-fit" asChild>
          <a href={downloadUrl} download={document.title}>
            <Download className="size-4" />
            {t("chat.download", { name: document.title })}
          </a>
        </Button>
      ) : null}
      <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4 text-sm leading-relaxed text-slate-200">
        {snippet ? snippet : <span className="text-slate-500">{t("documents.previewDocxNoSnippet")}</span>}
      </div>
    </div>
  );
}
