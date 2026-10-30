"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

import { AuthGate } from "@/features/auth/auth-gate";
import { ChatPanel } from "@/features/chat/chat-panel";
import { ChatSessionPicker } from "@/features/chat/chat-session-picker";
import { ChatSessionList } from "@/features/chat/chat-session-list";
import { PaneRail } from "@/features/chat/pane-rail";
import { PdfPane } from "@/features/chat/pdf-pane";
import { SplitPane } from "@/features/chat/split-pane";
import { useChatStore } from "@/features/chat/stores/chat-store";
import { hydrateLayout, useLayoutStore } from "@/features/chat/stores/layout-store";
import { hydratePaneOpen, useViewerStore } from "@/features/chat/stores/viewer-store";
import { useI18n } from "@/i18n/locale-provider";
import type { Citation } from "@/types/chat";

function subscribeDesktop(onChange: () => void) {
  const mq = window.matchMedia("(min-width: 1024px)");
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

export function ChatWorkspace({ sessionId }: { sessionId?: string }) {
  const { t } = useI18n();
  const storeSessionId = useChatStore((state) => state.sessionId);
  const target = useViewerStore((state) => state.target);
  const paneOpen = useViewerStore((state) => state.paneOpen);
  const openCitation = useViewerStore((state) => state.openCitation);
  const closePane = useViewerStore((state) => state.closePane);
  const openPane = useViewerStore((state) => state.openPane);
  const sessionsOpen = useLayoutStore((state) => state.sessionsOpen);
  const closeSessions = useLayoutStore((state) => state.closeSessions);
  const openSessions = useLayoutStore((state) => state.openSessions);
  const [mobilePdf, setMobilePdf] = useState(false);
  const desktop = useSyncExternalStore(
    subscribeDesktop,
    () => window.matchMedia("(min-width: 1024px)").matches,
    () => false,
  );
  const activeId = sessionId || storeSessionId;

  useEffect(() => {
    hydratePaneOpen();
    hydrateLayout();
  }, []);

  function onSelectCitation(citation: Citation) {
    openCitation(citation);
    setMobilePdf(true);
  }

  const chat = (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col">
      <ChatSessionPicker currentId={activeId} />
      <ChatPanel sessionId={sessionId} onSelectCitation={onSelectCitation} />
    </div>
  );

  return (
    <AuthGate>
      {desktop ? (
        <div className="flex min-h-0 min-w-0 flex-1">
          {sessionsOpen ? (
            <ChatSessionList currentId={activeId} onClose={closeSessions} />
          ) : (
            <PaneRail side="left" label={t("chat.showSessionsPane")} onClick={openSessions} />
          )}
          <SplitPane
            collapsed={!paneOpen}
            onCollapsedChange={(collapsed) => {
              if (collapsed) closePane();
              else openPane();
            }}
            left={<ChatPanel sessionId={sessionId} onSelectCitation={onSelectCitation} />}
            right={<PdfPane target={target} onClose={closePane} />}
          />
          {paneOpen ? null : (
            <PaneRail side="right" label={t("chat.showDocumentPane")} onClick={openPane} />
          )}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1">
          {mobilePdf ? (
            <PdfPane target={target} onBack={() => setMobilePdf(false)} />
          ) : (
            chat
          )}
        </div>
      )}
    </AuthGate>
  );
}
