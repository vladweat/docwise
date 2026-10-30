"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { useToastStore } from "@/stores/toast-store";
import { cn } from "@/lib/utils";
import { scrollToLatestToastStack } from "@/components/toast-stack";

export function ToastHost() {
  const { t } = useI18n();
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);
  const stackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollToLatestToastStack(stackRef.current);
  }, [toasts]);

  if (toasts.length === 0) return null;

  return (
    <div
      ref={stackRef}
      className="pointer-events-none fixed bottom-[calc(5rem+env(safe-area-inset-bottom))] left-3 right-3 z-50 flex max-h-[calc(100dvh-7rem)] flex-col gap-3 overflow-y-auto overscroll-contain sm:bottom-auto sm:left-auto sm:right-4 sm:top-16 sm:max-h-[calc(100dvh-6rem)] sm:w-[min(24rem,calc(100vw-2rem))]"
    >
      {toasts.map((toast) => (
        <Alert
          key={toast.id}
          variant={toast.variant === "error" ? "destructive" : "default"}
          className={cn(
            "pointer-events-auto flex shrink-0 flex-col items-stretch gap-2 rounded-xl border bg-slate-950 px-4 py-3 shadow-xl",
            toast.variant === "error" ? "border-red-800/80" : "border-slate-700",
          )}
          role={toast.variant === "error" ? "alert" : "status"}
        >
          <div className="flex items-start gap-2">
            <p className="min-w-0 flex-1">{toast.message}</p>
            <button
              type="button"
              className="shrink-0 rounded p-0.5 text-current/70 hover:text-current"
              aria-label={t("common.close")}
              onClick={() => dismiss(toast.id)}
            >
              <X className="size-4" />
            </button>
          </div>
          {toast.action ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              className="self-start"
              onClick={() => {
                toast.action?.onClick();
                dismiss(toast.id);
              }}
            >
              {toast.action.label}
            </Button>
          ) : null}
        </Alert>
      ))}
    </div>
  );
}
