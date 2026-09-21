import { create } from "zustand";

import type { Citation } from "@/types/chat";

export const PANE_OPEN_STORAGE_KEY = "dw-pdf-pane-open";

export interface ViewerTarget {
  docId: string;
  docTitle: string;
  format: "pdf" | "docx";
  page: number;
  section?: string | null;
  snippet: string;
}

function formatForTitle(title: string): "pdf" | "docx" {
  return title.toLowerCase().endsWith(".docx") ? "docx" : "pdf";
}

interface ViewerState {
  target: ViewerTarget | null;
  paneOpen: boolean;
  openCitation: (citation: Citation) => void;
  closePane: () => void;
  openPane: () => void;
  clear: () => void;
}

function persistPaneOpen(open: boolean) {
  try {
    localStorage.setItem(PANE_OPEN_STORAGE_KEY, open ? "1" : "0");
  } catch {
    // ignore
  }
}

export function hydratePaneOpen() {
  try {
    const raw = localStorage.getItem(PANE_OPEN_STORAGE_KEY);
    if (raw === "0") useViewerStore.setState({ paneOpen: false });
    if (raw === "1") useViewerStore.setState({ paneOpen: true });
  } catch {
    // ignore
  }
}

export const useViewerStore = create<ViewerState>((set) => ({
  target: null,
  paneOpen: true,
  openCitation: (citation) => {
    persistPaneOpen(true);
    set({
      paneOpen: true,
      target: {
        docId: citation.doc_id,
        docTitle: citation.doc_title,
        format: formatForTitle(citation.doc_title),
        page: citation.page ?? 0,
        section: citation.section,
        snippet: citation.snippet,
      },
    });
  },
  closePane: () => {
    persistPaneOpen(false);
    set({ paneOpen: false });
  },
  openPane: () => {
    persistPaneOpen(true);
    set({ paneOpen: true });
  },
  clear: () => set({ target: null }),
}));
