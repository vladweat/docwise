"use client";

import { X } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { useToastStore } from "@/stores/toast-store";
import { cn } from "@/lib/utils";

export function ToastHost() {
  const { t } = useI18n();
  const toasts = useToastStore((state) => state.toasts);
  const dismiss = useToastStore((state) => state.dismiss);

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed right-3 top-16 z-50 flex w-[min(24rem,calc(100vw-1.5rem))] flex-col gap-2 sm:right-4">
      {toasts.map((toast) => (
        <Alert
          key={toast.id}
          variant={toast.variant === "error" ? "destructive" : "default"}
          className={cn("pointer-events-auto flex flex-col items-stretch gap-2 py-2.5 shadow-lg")}
          role="status"
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
