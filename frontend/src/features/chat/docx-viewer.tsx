"use client";

import { Download, LoaderCircle } from "lucide-react";
import { type ReactNode, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiRequestError, fetchDocumentRaw } from "@/lib/api";
import type { ViewerTarget } from "@/features/chat/stores/viewer-store";

function highlightSnippet(text: string, snippet: string): ReactNode {
  const needle = snippet.trim();
  if (!needle) return text;
  const index = text.toLowerCase().indexOf(needle.toLowerCase());
  if (index < 0) return text;
  return (
    <>
      {text.slice(0, index)}
      <mark className="rounded bg-amber-400/30 px-0.5 text-amber-50">{text.slice(index, index + needle.length)}</mark>
      {text.slice(index + needle.length)}
    </>
  );
}

export function DocxViewer({ target }: { target: ViewerTarget }) {
  const [snippet, setSnippet] = useState(target.snippet);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);

  const sectionLabel = useMemo(
    () => target.section?.trim() || "раздел не указан",
    [target.section],
  );

  useEffect(() => {
    setSnippet(target.snippet);
    setError(null);
    let objectUrl: string | null = null;
    setLoading(true);
    void fetchDocumentRaw(target.docId)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setDownloadUrl(objectUrl);
      })
      .catch((err) => {
        const message =
          err instanceof ApiRequestError ? err.message : "Не удалось загрузить DOCX";
        setError(message);
      })
      .finally(() => setLoading(false));

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [target.docId]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-4">
      <p className="text-xs text-slate-500">
        Word-документ: цитата по разделу «{sectionLabel}». Полный просмотр — скачайте файл.
      </p>
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <LoaderCircle className="size-4 animate-spin" />
          Загрузка…
        </div>
      ) : null}
      {error ? <p className="text-sm text-red-400">{error}</p> : null}
      {downloadUrl ? (
        <Button type="button" variant="secondary" size="sm" className="w-fit" asChild>
          <a href={downloadUrl} download={target.docTitle}>
            <Download className="size-4" />
            Скачать {target.docTitle}
          </a>
        </Button>
      ) : null}
      <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-4 text-sm leading-relaxed text-slate-200">
        {highlightSnippet(snippet, target.snippet)}
      </div>
    </div>
  );
}
