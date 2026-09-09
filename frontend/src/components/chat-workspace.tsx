"use client";

import { useState } from "react";

import { AuthGate } from "@/components/auth-gate";
import { ChatPanel } from "@/components/chat-panel";
import { ChatSessionList } from "@/components/chat-session-list";
import { PdfPane, PdfPlaceholder } from "@/components/pdf-pane";
import { SplitPane } from "@/components/split-pane";
import { useChatStore } from "@/stores/chat-store";
import { useViewerStore } from "@/stores/viewer-store";
import type { Citation } from "@/types/chat";

export function ChatWorkspace({ sessionId }: { sessionId?: string }) {
  const storeSessionId = useChatStore((state) => state.sessionId);
  const target = useViewerStore((state) => state.target);
  const openCitation = useViewerStore((state) => state.openCitation);
  const [mobilePdf, setMobilePdf] = useState(false);
  const activeId = sessionId || storeSessionId;

  function onSelectCitation(citation: Citation) {
    openCitation(citation);
    setMobilePdf(true);
  }

  const chat = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col md:flex-row">
      <ChatSessionList currentId={activeId} />
      <ChatPanel sessionId={sessionId} onSelectCitation={onSelectCitation} />
    </div>
  );

  return (
    <AuthGate>
      <div className="flex min-h-0 flex-1 lg:hidden">
        {mobilePdf ? (
          <PdfPane target={target} onBack={() => setMobilePdf(false)} />
        ) : (
          chat
        )}
      </div>
      <div className="hidden min-h-0 flex-1 lg:flex">
        <SplitPane
          left={chat}
          right={target ? <PdfPane target={target} /> : <PdfPlaceholder />}
        />
      </div>
    </AuthGate>
  );
}
