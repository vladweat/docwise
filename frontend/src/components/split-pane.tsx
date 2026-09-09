"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const STORAGE_KEY = "dw-split-left-pct";
const DEFAULT_PCT = 45;
const MIN_PCT = 28;
const MAX_PCT = 70;

export function SplitPane({
  left,
  right,
}: {
  left: ReactNode;
  right: ReactNode;
}) {
  const [leftPct, setLeftPct] = useState(DEFAULT_PCT);
  const dragging = useRef(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const pctRef = useRef(leftPct);
  pctRef.current = leftPct;

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const value = raw ? Number(raw) : NaN;
      if (value >= MIN_PCT && value <= MAX_PCT) setLeftPct(value);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      if (!dragging.current || !rootRef.current) return;
      event.preventDefault();
      const rect = rootRef.current.getBoundingClientRect();
      const next = ((event.clientX - rect.left) / rect.width) * 100;
      setLeftPct(Math.min(MAX_PCT, Math.max(MIN_PCT, next)));
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
  }, []);

  return (
    <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1">
      <div className="flex min-h-0 min-w-0 flex-col" style={{ width: `${leftPct}%` }}>
        {left}
      </div>
      <button
        type="button"
        aria-label="Изменить ширину панелей"
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
      >
        <span className="absolute inset-y-0 -left-1 -right-1" />
      </button>
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">{right}</div>
    </div>
  );
}
