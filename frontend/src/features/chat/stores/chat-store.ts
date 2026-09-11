import { create } from "zustand";

import type { Citation } from "@/types/chat";

export interface UiMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Citation[];
  created_at: string;
  cached?: boolean;
  error?: boolean;
  serverId?: string | null;
}

interface ChatState {
  sessionId: string | null;
  messages: UiMessage[];
  sending: boolean;
  loadedFor: string | null;
  setSending: (sending: boolean) => void;
  resetNew: () => void;
  hydrate: (sessionId: string, messages: UiMessage[]) => void;
  setSessionId: (sessionId: string) => void;
  appendMessages: (messages: UiMessage[]) => void;
  patchMessage: (id: string, patch: Partial<UiMessage> | ((item: UiMessage) => UiMessage)) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  sessionId: null,
  messages: [],
  sending: false,
  loadedFor: null,
  setSending: (sending) => set({ sending }),
  resetNew: () => set({ sessionId: null, messages: [], sending: false, loadedFor: "" }),
  hydrate: (sessionId, messages) =>
    set({ sessionId, messages, sending: false, loadedFor: sessionId }),
  setSessionId: (sessionId) => set({ sessionId, loadedFor: sessionId }),
  appendMessages: (messages) => set((state) => ({ messages: [...state.messages, ...messages] })),
  patchMessage: (id, patch) =>
    set((state) => ({
      messages: state.messages.map((item) => {
        if (item.id !== id) return item;
        return typeof patch === "function" ? patch(item) : { ...item, ...patch };
      }),
    })),
}));
