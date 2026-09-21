"use client";

import { useState } from "react";
import Link from "next/link";
import { MessageSquarePlus } from "lucide-react";

import { DocumentUploadModal } from "@/features/documents/document-upload-modal";
import { useAuth } from "@/features/auth/auth-provider";
import { useCorpusReady } from "@/features/chat/lib/use-corpus-ready";
import { chatSuggestionKeysFor, isDemoOrganization } from "@/features/chat/lib/chat-suggestions";
import { startNewChatSession } from "@/features/chat/lib/new-session";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { canManageKnowledgeBase } from "@/lib/access-roles";

export function ChatEmptyState({
  onSend,
  onStartNew,
}: {
  onSend: (text: string) => void;
  onStartNew?: () => void;
}) {
  const { t } = useI18n();
  const { user } = useAuth();
  const { hasReadyCorpus, loading: corpusLoading } = useCorpusReady();
  const demoOrg = isDemoOrganization(user);
  const canManage = canManageKnowledgeBase(user);
  const [uploadOpen, setUploadOpen] = useState(false);

  const showGuidedEmpty = !corpusLoading && !hasReadyCorpus;
  const suggestionKeys = chatSuggestionKeysFor(user);

  function handleNewSession() {
    startNewChatSession();
    onStartNew?.();
  }

  if (showGuidedEmpty) {
    return (
      <>
        <div className="flex flex-1 flex-col items-center justify-center gap-5 py-6 text-center sm:py-10">
          <div>
            <h2 className="text-lg font-semibold sm:text-xl">{t("chat.emptyCorpusTitle")}</h2>
            <p className="mt-2 max-w-md text-sm text-slate-400">{t("chat.emptyCorpusIntro")}</p>
          </div>
          {canManage ? (
            <div className="flex w-full max-w-md flex-col gap-3 text-left">
              <Alert>{t("chat.emptyCorpusAdminHint")}</Alert>
              <Button type="button" className="w-full" onClick={() => setUploadOpen(true)}>
                {t("chat.emptyCorpusUpload")}
              </Button>
            </div>
          ) : (
            <div className="flex w-full max-w-md flex-col gap-3">
              <Alert className="text-left">{t("chat.emptyCorpusEmployeeHint")}</Alert>
              <Button asChild variant="outline" className="w-full">
                <Link href="/documents">{t("chat.emptyCorpusViewDocuments")}</Link>
              </Button>
            </div>
          )}
          <MobileEmptyExtras onNewSession={handleNewSession} />
        </div>
        <DocumentUploadModal open={uploadOpen} onClose={() => setUploadOpen(false)} />
      </>
    );
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-5 py-6 text-center sm:py-10">
      <div>
        <h2 className="text-lg font-semibold sm:text-xl">{t("chat.askTitle")}</h2>
        <p className="mt-2 max-w-md text-sm text-slate-400">{t("chat.askIntro")}</p>
      </div>
      {demoOrg ? <Alert className="max-w-md text-left">{t("chat.demoHint")}</Alert> : null}
      <div className="flex w-full flex-col gap-2">
        {suggestionKeys.map((key) => {
          const label = t(key);
          return (
            <Button
              key={key}
              type="button"
              variant="outline"
              onClick={() => void onSend(label)}
              className="h-auto justify-start whitespace-normal rounded-xl px-4 py-3 text-left font-normal"
            >
              {label}
            </Button>
          );
        })}
      </div>
      <MobileEmptyExtras onNewSession={handleNewSession} />
    </div>
  );
}

function MobileEmptyExtras({ onNewSession }: { onNewSession: () => void }) {
  const { t } = useI18n();
  return (
    <div className="flex w-full max-w-md flex-col items-center gap-2 border-t border-slate-800/80 pt-4 lg:hidden">
      <Button type="button" variant="ghost" size="sm" className="gap-2" onClick={onNewSession}>
        <MessageSquarePlus className="size-4" />
        {t("chat.newSession")}
      </Button>
      <p className="text-xs text-slate-500">{t("chat.mobileCitationHint")}</p>
    </div>
  );
}
