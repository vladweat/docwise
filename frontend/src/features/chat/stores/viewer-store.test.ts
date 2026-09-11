import { afterEach, describe, expect, it } from "vitest";

import { useViewerStore } from "@/features/chat/stores/viewer-store";
import type { Citation } from "@/types/chat";

const CITATION: Citation = {
  doc_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  doc_title: "Handbook.pdf",
  page: 4,
  snippet: "vacation",
};

afterEach(() => {
  useViewerStore.getState().clear();
  useViewerStore.setState({ paneOpen: true, target: null });
});

describe("openCitation", () => {
  it("reopens the PDF pane on the cited page", () => {
    useViewerStore.setState({ paneOpen: false, target: null });
    useViewerStore.getState().openCitation(CITATION);
    const state = useViewerStore.getState();
    expect(state.paneOpen).toBe(true);
    expect(state.target).toEqual({
      docId: CITATION.doc_id,
      docTitle: CITATION.doc_title,
      page: 4,
      snippet: "vacation",
    });
  });
});
