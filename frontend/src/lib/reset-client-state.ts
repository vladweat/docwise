import type { QueryClient } from "@tanstack/react-query";

import { useChatStore } from "@/stores/chat-store";
import { useViewerStore } from "@/stores/viewer-store";

/** Drop cached sessions, documents, and in-memory chat when the user identity changes. */
export function resetClientSessionState(queryClient: QueryClient) {
  queryClient.clear();
  useChatStore.getState().resetNew();
  useViewerStore.getState().clear();
}
