"use client";

import { useState } from "react";
import { PanelLeftOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ChatSessionList } from "@/features/chat/chat-session-list";
import { useI18n } from "@/i18n/locale-provider";

export function ChatSessionPicker({ currentId }: { currentId?: string | null }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <div className="flex shrink-0 items-center border-b border-slate-800 px-3 py-1.5">
        <DialogTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="gap-2 text-slate-300"
            aria-label={t("chat.sessions")}
          >
            <PanelLeftOpen className="size-4" />
            {t("chat.sessions")}
          </Button>
        </DialogTrigger>
      </div>
      <DialogContent
        className="grid h-[min(42dvh,24rem)] min-h-60 grid-rows-[auto_minmax(0,1fr)] gap-2 overflow-hidden p-4 lg:h-[min(80dvh,36rem)] lg:min-h-0 lg:gap-4 lg:p-5"
        showCloseButton
      >
        <ChatSessionList
          currentId={currentId}
          onClose={() => setOpen(false)}
          dialogMode
        />
      </DialogContent>
    </Dialog>
  );
}
