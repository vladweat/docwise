"use client";

import { X } from "lucide-react";

import { useToastStore } from "@/stores/toast-store";
import { cn } from "@/lib/utils";

export function ToastHost() {
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-3 top-16 z-50 flex w-[min(24rem,calc(100vw-1.5rem))] flex-col gap-2 sm:right-4">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={cn(
            "pointer-events-auto flex items-start gap-2 rounded-xl border px-3 py-2.5 text-sm shadow-lg",
            toast.variant === "error"
              ? "border-red-500/40 bg-red-950/90 text-red-100"
              : "border-slate-700 bg-slate-900/95 text-slate-100",
          )}
          role="status"
        >
          <p className="min-w-0 flex-1">{toast.message}</p>
          <button
            type="button"
            className="shrink-0 rounded p-0.5 text-current/70 hover:text-current"
            aria-label="Закрыть"
            onClick={() => dismiss(toast.id)}
          >
            <X className="size-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
