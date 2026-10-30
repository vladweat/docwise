import { create } from "zustand";

export interface ToastAction {
  label: string;
  onClick: () => void;
}

export interface Toast {
  id: string;
  message: string;
  variant: "error" | "info";
  action?: ToastAction;
}

interface ToastState {
  toasts: Toast[];
  push: (message: string, variant?: Toast["variant"], action?: ToastAction) => void;
  dismiss: (id: string) => void;
}

const MAX_VISIBLE_TOASTS = 3;
const toastTimers = new Map<string, ReturnType<typeof setTimeout>>();

function scheduleDismiss(id: string, hasAction: boolean) {
  const previousTimer = toastTimers.get(id);
  if (previousTimer) clearTimeout(previousTimer);
  const timer = setTimeout(() => {
    toastTimers.delete(id);
    useToastStore.getState().dismiss(id);
  }, hasAction ? 12_000 : 6_000);
  toastTimers.set(id, timer);
}

function clearDismiss(id: string) {
  const timer = toastTimers.get(id);
  if (timer) clearTimeout(timer);
  toastTimers.delete(id);
}

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (message, variant = "error", action) => {
    const existing = get().toasts.find(
      (toast) => toast.message === message && toast.variant === variant,
    );
    if (existing) {
      if (action) {
        set((state) => ({
          toasts: state.toasts.map((toast) =>
            toast.id === existing.id ? { ...toast, action } : toast,
          ),
        }));
      }
      scheduleDismiss(existing.id, Boolean(action || existing.action));
      return;
    }

    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const next = [...get().toasts, { id, message, variant, action }];
    const dropped = next.slice(0, Math.max(0, next.length - MAX_VISIBLE_TOASTS));
    dropped.forEach((toast) => clearDismiss(toast.id));
    set({ toasts: next.slice(-MAX_VISIBLE_TOASTS) });
    scheduleDismiss(id, Boolean(action));
  },
  dismiss: (id) => {
    clearDismiss(id);
    set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) }));
  },
}));
