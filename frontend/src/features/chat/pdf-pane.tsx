"use client";

import { ChevronLeft, FileText } from "lucide-react";
import dynamic from "next/dynamic";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/i18n/locale-provider";
import type { ViewerTarget } from "@/features/chat/stores/viewer-store";

const PdfViewer = dynamic(() => import("@/features/chat/pdf-viewer").then((mod) => mod.PdfViewer), {
  ssr: false,
  loading: () => (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-[70%] w-[90%]" />
    </div>
  ),
});

const DocxViewer = dynamic(() => import("@/features/chat/docx-viewer").then((mod) => mod.DocxViewer), {
  ssr: false,
  loading: () => (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 p-6">
      <Skeleton className="h-8 w-40" />
      <Skeleton className="h-[40%] w-[90%]" />
    </div>
  ),
});

export function PdfPlaceholder() {
  const { t } = useI18n();
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <FileText className="size-10 text-slate-600" />
      <p className="max-w-sm text-sm text-slate-400">{t("chat.pickCitation")}</p>
    </div>
  );
}

export function PdfPane({
  target,
  onBack,
}: {
  target: ViewerTarget | null;
  onBack?: () => void;
}) {
  const { t } = useI18n();
  return (
    <div className="flex min-h-0 flex-1 flex-col bg-slate-950">
      <div className="flex shrink-0 items-center gap-2 border-b border-slate-800 px-2 py-1.5">
        {onBack ? (
          <Button type="button" variant="ghost" size="sm" className="lg:hidden" onClick={onBack}>
            <ChevronLeft />
            {t("chat.backToChat")}
          </Button>
        ) : null}
        <div className="min-w-0 flex-1">
          {target ? (
            <>
              <p className="truncate text-sm font-medium text-slate-100">{target.docTitle}</p>
              <p className="text-[11px] text-slate-500">
                {target.format === "docx"
                  ? `${t("chat.sectionPrefix")} ${target.section?.trim() || "—"}`
                  : `${t("chat.pageShort")} ${target.page}`}
                {target.snippet && target.format === "pdf" ? t("chat.snippetHighlighted") : ""}
              </p>
            </>
          ) : (
            <p className="truncate text-sm text-slate-500">{t("common.document")}</p>
          )}
        </div>
      </div>
      {target ? (
        target.format === "docx" ? <DocxViewer target={target} /> : <PdfViewer target={target} />
      ) : (
        <PdfPlaceholder />
      )}
    </div>
  );
}
