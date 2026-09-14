"use client";

import { ChevronLeft, ChevronRight, LoaderCircle, ZoomIn, ZoomOut } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiRequestError, fetchDocumentPdf } from "@/lib/api";
import { cn } from "@/lib/utils";

const pdfBufferCache = new Map<string, Promise<ArrayBuffer>>();

function loadPdfBuffer(documentId: string): Promise<ArrayBuffer> {
  const hit = pdfBufferCache.get(documentId);
  if (hit) return hit;
  const next = fetchDocumentPdf(documentId)
    .then((blob) => blob.arrayBuffer())
    .catch((err) => {
      pdfBufferCache.delete(documentId);
      throw err;
    });
  pdfBufferCache.set(documentId, next);
  return next;
}

const MIN_ZOOM = 0.5;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.25;
const PAGE_PADDING = 32;

export function DocumentPdfPreview({ documentId }: { documentId: string }) {
  const measureRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const renderTaskRef = useRef<{ cancel: () => void } | null>(null);
  const [fitWidth, setFitWidth] = useState(0);
  const [pageCount, setPageCount] = useState(0);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(1);
    setZoom(1);
    setPageCount(0);
    setError(null);
    setCanvasSize({ width: 0, height: 0 });
  }, [documentId]);

  useEffect(() => {
    const el = measureRef.current;
    if (!el) return;

    const updateWidth = (width: number) => {
      if (width < 40) return;
      setFitWidth((prev) => (Math.abs(prev - width) < 4 ? prev : width));
    };

    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      updateWidth(width);
    });
    observer.observe(el);
    updateWidth(el.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (fitWidth < 40) return;
    let cancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      renderTaskRef.current?.cancel();
      renderTaskRef.current = null;

      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const data = await loadPdfBuffer(documentId);
        if (cancelled) return;

        const pdf = await pdfjs.getDocument({ data: new Uint8Array(data.slice(0)) }).promise;
        if (cancelled) return;

        setPageCount(pdf.numPages);
        const pageNumber = Math.min(Math.max(page, 1), pdf.numPages);
        const pdfPage = await pdf.getPage(pageNumber);
        if (cancelled) return;

        const unscaled = pdfPage.getViewport({ scale: 1 });
        const fitScale = Math.max(0.1, (fitWidth - PAGE_PADDING) / unscaled.width);
        const scale = fitScale * zoom;
        const viewport = pdfPage.getViewport({ scale });

        const canvas = canvasRef.current;
        if (!canvas) return;
        const context = canvas.getContext("2d");
        if (!context) return;

        const outputScale = window.devicePixelRatio || 1;
        canvas.width = Math.floor(viewport.width * outputScale);
        canvas.height = Math.floor(viewport.height * outputScale);
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        context.setTransform(outputScale, 0, 0, outputScale, 0, 0);

        const task = pdfPage.render({ canvasContext: context, viewport });
        renderTaskRef.current = task;
        await task.promise;
        if (cancelled) return;

        setCanvasSize({ width: viewport.width, height: viewport.height });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof Error && err.message.toLowerCase().includes("cancel")) return;
        const message =
          err instanceof ApiRequestError && err.status === 404
            ? "Документ недоступен"
            : err instanceof ApiRequestError
              ? err.message
              : "Не удалось открыть документ";
        setError(message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void run();
    return () => {
      cancelled = true;
      renderTaskRef.current?.cancel();
      renderTaskRef.current = null;
    };
  }, [documentId, fitWidth, page, zoom]);

  const zoomOut = useCallback(() => {
    setZoom((value) => Math.max(MIN_ZOOM, Number((value - ZOOM_STEP).toFixed(2))));
  }, []);

  const zoomIn = useCallback(() => {
    setZoom((value) => Math.min(MAX_ZOOM, Number((value + ZOOM_STEP).toFixed(2))));
  }, []);

  const resetZoom = useCallback(() => setZoom(1), []);

  return (
    <div className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden bg-slate-950">
      <div className="shrink-0 border-b border-slate-800 px-3 py-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={page <= 1 || loading}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              aria-label="Предыдущая страница"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-20 text-center text-sm text-slate-300">
              {pageCount > 0 ? `${page} / ${pageCount}` : "—"}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={page >= pageCount || loading}
              onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
              aria-label="Следующая страница"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
          <div className="flex items-center gap-1">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={loading || zoom <= MIN_ZOOM}
              onClick={zoomOut}
              aria-label="Уменьшить"
            >
              <ZoomOut className="size-4" />
            </Button>
            <button
              type="button"
              className={cn(
                "min-w-14 rounded-md px-2 py-1 text-sm text-slate-300 hover:bg-slate-800",
                loading && "pointer-events-none opacity-50",
              )}
              onClick={resetZoom}
              aria-label="Сбросить масштаб"
            >
              {Math.round(zoom * 100)}%
            </button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              disabled={loading || zoom >= MAX_ZOOM}
              onClick={zoomIn}
              aria-label="Увеличить"
            >
              <ZoomIn className="size-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="relative min-h-0 min-w-0 flex-1 overflow-hidden">
        <div ref={measureRef} className="pointer-events-none absolute inset-x-0 top-0 h-0" aria-hidden />
        {loading ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/60 text-sm text-slate-400">
            <LoaderCircle className="mr-2 size-4 animate-spin" />
            Загрузка PDF…
          </div>
        ) : null}
        {error ? (
          <p className="absolute inset-x-0 top-4 z-20 px-4 text-center text-sm text-red-400">{error}</p>
        ) : null}
        <div className="h-full min-h-0 overflow-auto">
          <div className="flex min-h-full justify-center p-4">
            <canvas
              ref={canvasRef}
              className="block max-w-none shrink-0 rounded-sm bg-white shadow-lg"
              style={{
                width: canvasSize.width ? `${canvasSize.width}px` : undefined,
                height: canvasSize.height ? `${canvasSize.height}px` : undefined,
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
