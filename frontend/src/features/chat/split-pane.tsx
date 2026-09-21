"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { useI18n } from "@/i18n/locale-provider";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "dw-split-chat-pct";
const DEFAULT_PCT = 45;
const CHAT_MIN_PX = 440;
const PDF_MIN_PX = 320;

function clampChatWidth(desired: number, total: number): number {
  if (total <= 0) return 0;
  const minChat = Math.min(CHAT_MIN_PX, total);
  const leftover = Math.max(0, total - minChat);
  const pdfMin = leftover >= PDF_MIN_PX ? PDF_MIN_PX : leftover;
  const maxChat = Math.max(minChat, total - pdfMin);
  return Math.min(Math.max(desired, minChat), maxChat);
}

export function SplitPane({
  left,
  right,
  collapsed = false,
  onCollapsedChange,
}: {
  left: ReactNode;
  right: ReactNode;
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
}) {
  const { t } = useI18n();
  const [chatWidth, setChatWidth] = useState(0);
  const dragging = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const pctRef = useRef(DEFAULT_PCT);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const value = raw ? Number(raw) : NaN;
      if (value >= 20 && value <= 80) pctRef.current = value;
    } catch {
      // ignore
    }

    const el = rootRef.current;
    if (!el) return;

    const apply = () => {
      const total = el.getBoundingClientRect().width;
      if (collapsed) {
        setChatWidth(total);
        return;
      }
      setChatWidth(clampChatWidth((pctRef.current / 100) * total, total));
    };

    const observer = new ResizeObserver(apply);
    observer.observe(el);
    apply();
    return () => observer.disconnect();
  }, [collapsed]);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!dragging.current || !rootRef.current || collapsed) return;
      event.preventDefault();
      const rect = rootRef.current.getBoundingClientRect();
      const next = clampChatWidth(event.clientX - rect.left, rect.width);
      pctRef.current = rect.width > 0 ? (next / rect.width) * 100 : pctRef.current;
      setChatWidth(next);
    };
    const onUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      try {
        localStorage.setItem(STORAGE_KEY, String(Math.round(pctRef.current)));
      } catch {
        // ignore
      }
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [collapsed]);

  return (
    <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 overflow-hidden">
      <div
        className={cn(
          "flex min-h-0 min-w-0 flex-col overflow-hidden",
          collapsed || chatWidth <= 0 ? "flex-1" : "shrink-0",
        )}
        style={collapsed || chatWidth <= 0 ? undefined : { width: chatWidth }}
      >
        {left}
      </div>
      {collapsed ? null : (
        <button
          type="button"
          aria-label={t("chat.resizePanes")}
          title={t("chat.resizePanesHint")}
          className={cn(
            "group relative z-10 w-1.5 shrink-0 cursor-col-resize bg-slate-800 hover:bg-blue-500/70",
            "focus-visible:bg-blue-500/70 focus-visible:outline-none",
          )}
          onPointerDown={(event) => {
            event.preventDefault();
            dragging.current = true;
            document.body.style.cursor = "col-resize";
            document.body.style.userSelect = "none";
          }}
          onDoubleClick={() => onCollapsedChange?.(true)}
        >
          <span className="absolute inset-y-0 -left-1 -right-1" />
        </button>
      )}
      <div
        className={cn(
          "flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
          collapsed && "hidden",
        )}
        aria-hidden={collapsed}
      >
        {right}
      </div>
    </div>
  );
}
