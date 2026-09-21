import type { QueryClient } from "@tanstack/react-query";

import { useChatStore } from "@/features/chat/stores/chat-store";
import { useViewerStore } from "@/features/chat/stores/viewer-store";

export function startNewChatSession(queryClient?: QueryClient): void {
  useChatStore.getState().resetNew();
  useViewerStore.getState().clear();
  void queryClient?.invalidateQueries({ queryKey: ["chat-sessions"] });
}
