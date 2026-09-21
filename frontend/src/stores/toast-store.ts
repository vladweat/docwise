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

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (message, variant = "error", action) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    set((state) => ({
      toasts: [...state.toasts.slice(-4), { id, message, variant, action }],
    }));
    window.setTimeout(() => get().dismiss(id), action ? 12_000 : 6000);
  },
  dismiss: (id) => set((state) => ({ toasts: state.toasts.filter((item) => item.id !== id) })),
}));
