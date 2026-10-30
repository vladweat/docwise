"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import { PanelRightOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { AuthGate } from "@/features/auth/auth-gate";
import { ChatPanel } from "@/features/chat/chat-panel";
import { ChatSessionPicker } from "@/features/chat/chat-session-picker";
import { PdfPane } from "@/features/chat/pdf-pane";
import { SplitPane } from "@/features/chat/split-pane";
import { useChatStore } from "@/features/chat/stores/chat-store";
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
  const [mobilePdf, setMobilePdf] = useState(false);
  const desktop = useSyncExternalStore(
    subscribeDesktop,
    () => window.matchMedia("(min-width: 1024px)").matches,
    () => false,
  );
  const activeId = sessionId || storeSessionId;

  useEffect(() => {
    hydratePaneOpen();
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
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 px-3">
            <ChatSessionPicker currentId={activeId} className="border-0 px-0 py-0" />
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="gap-2 text-slate-300"
              aria-label={paneOpen ? t("chat.hideDocumentPane") : t("chat.showDocumentPane")}
              onClick={() => (paneOpen ? closePane() : openPane())}
            >
              <PanelRightOpen className="size-4" />
              {paneOpen ? t("chat.hideDocumentPane") : t("chat.showDocumentPane")}
            </Button>
          </div>
          <div className="flex min-h-0 min-w-0 flex-1">
            <SplitPane
              collapsed={!paneOpen}
              onCollapsedChange={(collapsed) => {
                if (collapsed) closePane();
                else openPane();
              }}
              left={<ChatPanel sessionId={sessionId} onSelectCitation={onSelectCitation} />}
              right={<PdfPane target={target} />}
            />
          </div>
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
