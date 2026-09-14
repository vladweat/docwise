"use client";

import { ChevronLeft, FileText, PanelRightClose } from "lucide-react";
import dynamic from "next/dynamic";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
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

function ClosePaneButton({ onClose }: { onClose?: () => void }) {
  if (!onClose) return null;
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="hidden size-8 shrink-0 lg:inline-flex"
      onClick={onClose}
      aria-label="Скрыть панель документа"
      title="Скрыть панель документа"
    >
      <PanelRightClose />
    </Button>
  );
}

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
  onClose,
}: {
  target: ViewerTarget | null;
  onBack?: () => void;
  onClose?: () => void;
}) {
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
          {target ? (
            <>
              <p className="truncate text-sm font-medium text-slate-100">{target.docTitle}</p>
              <p className="text-[11px] text-slate-500">
                стр. {target.page}
                {target.snippet ? " · фрагмент подсвечен" : ""}
              </p>
            </>
          ) : (
            <p className="truncate text-sm text-slate-500">Документ</p>
          )}
        </div>
        <ClosePaneButton onClose={onClose} />
      </div>
      {target ? <PdfViewer target={target} /> : <PdfPlaceholder />}
    </div>
  );
}
