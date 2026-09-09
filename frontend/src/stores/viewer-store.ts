import { create } from "zustand";

import type { Citation } from "@/types/chat";

export interface ViewerTarget {
  docId: string;
  docTitle: string;
  page: number;
  snippet: string;
}

interface ViewerState {
  target: ViewerTarget | null;
  openCitation: (citation: Citation) => void;
  clear: () => void;
}

export const useViewerStore = create<ViewerState>((set) => ({
  target: null,
  openCitation: (citation) =>
    set({
      target: {
        docId: citation.doc_id,
        docTitle: citation.doc_title,
        page: citation.page,
        snippet: citation.snippet,
      },
    }),
  clear: () => set({ target: null }),
}));
