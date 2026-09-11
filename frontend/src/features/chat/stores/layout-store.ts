import { create } from "zustand";

export const SESSIONS_OPEN_STORAGE_KEY = "dw-sessions-pane-open";

interface LayoutState {
  sessionsOpen: boolean;
  closeSessions: () => void;
  openSessions: () => void;
}

function persistSessionsOpen(open: boolean) {
  try {
    localStorage.setItem(SESSIONS_OPEN_STORAGE_KEY, open ? "1" : "0");
  } catch {
    // ignore
  }
}

export function hydrateLayout() {
  try {
    const raw = localStorage.getItem(SESSIONS_OPEN_STORAGE_KEY);
    if (raw === "0") useLayoutStore.setState({ sessionsOpen: false });
    if (raw === "1") useLayoutStore.setState({ sessionsOpen: true });
  } catch {
    // ignore
  }
}

export const useLayoutStore = create<LayoutState>((set) => ({
  sessionsOpen: true,
  closeSessions: () => {
    persistSessionsOpen(false);
    set({ sessionsOpen: false });
  },
  openSessions: () => {
    persistSessionsOpen(true);
    set({ sessionsOpen: true });
  },
}));
