"use client";

import { ChevronLeft, ChevronRight, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiRequestError, fetchDocumentPdf } from "@/lib/api";
import { findSnippetRects, type HighlightRect } from "@/features/chat/lib/pdf-highlight";
import { cn } from "@/lib/utils";
import type { ViewerTarget } from "@/features/chat/stores/viewer-store";

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

export function PdfViewer({ target }: { target: ViewerTarget }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [pageCount, setPageCount] = useState(0);
  const [page, setPage] = useState(target.page);
  const [highlights, setHighlights] = useState<HighlightRect[]>([]);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPage(target.page);
  }, [target.docId, target.page]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(el.clientWidth));
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (width < 40) return;
    let cancelled = false;

    const run = async () => {
      setLoading(true);
      setError(null);
      setHighlights([]);
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";
        const data = await loadPdfBuffer(target.docId);
        if (cancelled) return;
        const pdf = await pdfjs.getDocument({ data: new Uint8Array(data.slice(0)) }).promise;
        if (cancelled) return;
        setPageCount(pdf.numPages);
        const pageNumber = Math.min(Math.max(page, 1), pdf.numPages);
        const pdfPage = await pdf.getPage(pageNumber);
        if (cancelled) return;
        const unscaled = pdfPage.getViewport({ scale: 1 });
        const scale = (width - 16) / unscaled.width;
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
        await pdfPage.render({ canvasContext: context, viewport }).promise;
        if (cancelled) return;
        setCanvasSize({ width: viewport.width, height: viewport.height });

        if (pageNumber === target.page && target.snippet) {
          const content = await pdfPage.getTextContent();
          const items = content.items.flatMap((item) => {
            if (!("str" in item) || !item.str) return [];
            return [
              {
                str: item.str,
                transform: Array.from(item.transform ?? []),
                width: item.width ?? 0,
                height: item.height ?? 0,
              },
            ];
          });
          const rects = findSnippetRects(
            items,
            (rect) => viewport.convertToViewportRectangle(rect),
            target.snippet,
          );
          setHighlights(rects);
          const first = rects[0];
          const box = containerRef.current;
          if (first && box) {
            box.scrollTo({ top: Math.max(0, first.top - 32), behavior: "smooth" });
          }
        } else {
          setHighlights([]);
        }
      } catch (err) {
        if (cancelled) return;
        const message =
          err instanceof ApiRequestError
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
    };
  }, [target.docId, target.page, target.snippet, page, width]);

  return (
    <div ref={containerRef} className="relative min-h-0 flex-1 overflow-auto bg-slate-950">
      {loading ? (
        <div className="absolute inset-0 z-10 flex items-center justify-center bg-slate-950/50 text-sm text-slate-400">
          <LoaderCircle className="mr-2 size-4 animate-spin" />
          Загрузка PDF…
        </div>
      ) : null}
      {error ? (
        <p className="px-4 py-8 text-center text-sm text-red-400">{error}</p>
      ) : (
        <div className="flex justify-center p-2">
          <div className="relative" style={{ width: canvasSize.width || "auto" }}>
            <canvas ref={canvasRef} className="block rounded-sm bg-white shadow-lg" />
            {highlights.map((rect, index) => (
              <div
                key={index}
                className="pointer-events-none absolute rounded-sm bg-amber-300/45 ring-1 ring-amber-400/70"
                style={{
                  left: rect.left,
                  top: rect.top,
                  width: rect.width,
                  height: rect.height,
                }}
              />
            ))}
          </div>
        </div>
      )}
      {pageCount > 1 ? (
        <div className="sticky bottom-2 flex justify-center">
          <div className="flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/90 px-2 py-1 text-xs text-slate-300 shadow-lg">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              disabled={page <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              aria-label="Предыдущая страница"
            >
              <ChevronLeft />
            </Button>
            <span className={cn("min-w-16 text-center")}>
              {page} / {pageCount}
            </span>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7"
              disabled={page >= pageCount}
              onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
              aria-label="Следующая страница"
            >
              <ChevronRight />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
