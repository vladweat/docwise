"use client";

import { ChevronLeft, FileText } from "lucide-react";
import dynamic from "next/dynamic";

import { Button } from "@/components/ui/button";
import type { ViewerTarget } from "@/stores/viewer-store";

const PdfViewer = dynamic(() => import("@/components/pdf-viewer").then((mod) => mod.PdfViewer), {
  ssr: false,
  loading: () => (
    <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
      Загрузка PDF…
    </div>
  ),
});

export function PdfPlaceholder() {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
      <FileText className="size-10 text-slate-600" />
      <p className="max-w-sm text-sm text-slate-400">
        Выберите цитату, чтобы открыть источник
      </p>
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
  if (!target) {
    return (
      <div className="flex min-h-0 flex-1 flex-col bg-slate-950">
        {onBack ? (
          <div className="shrink-0 border-b border-slate-800 px-2 py-1.5 lg:hidden">
            <Button type="button" variant="ghost" size="sm" onClick={onBack}>
              <ChevronLeft />
              К чату
            </Button>
          </div>
        ) : null}
        <PdfPlaceholder />
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-slate-950">
      <div className="flex shrink-0 items-center gap-2 border-b border-slate-800 px-2 py-1.5">
        {onBack ? (
          <Button type="button" variant="ghost" size="sm" className="lg:hidden" onClick={onBack}>
            <ChevronLeft />
            К чату
          </Button>
        ) : null}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-100">{target.docTitle}</p>
          <p className="text-[11px] text-slate-500">стр. {target.page}</p>
        </div>
      </div>
      <PdfViewer target={target} />
    </div>
  );
}
