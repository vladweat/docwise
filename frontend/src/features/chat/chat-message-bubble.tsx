"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";

import { AnswerMarkdown } from "@/features/chat/answer-markdown";
import { CitationTag } from "@/features/chat/citation-tag";
import {
  isNoContextAnswer,
  splitAnswerParts,
  stripCitationMarkers,
  uniqueCitations,
} from "@/features/chat/lib/chat";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/i18n/locale-provider";
import { ApiRequestError, sendChatFeedback } from "@/lib/api";
import { userFacingApiMessage } from "@/lib/quota";
import { cn } from "@/lib/utils";
import { useChatStore, type UiMessage } from "@/features/chat/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import type { Citation } from "@/types/chat";

export function ChatMessageBubble({
  message,
  streaming,
  onSelectCitation,
}: {
  message: UiMessage;
  streaming: boolean;
  onSelectCitation?: (citation: Citation) => void;
}) {
  const { t } = useI18n();
  const [savingFeedback, setSavingFeedback] = useState(false);
  const isUser = message.role === "user";
  const chips = uniqueCitations(message.sources);
  const parts = splitAnswerParts(message.content, message.sources);
  const plainContent = chips.length > 0 ? stripCitationMarkers(message.content) : message.content;
  const isRefusal = isNoContextAnswer(message.content);
  const canFeedback =
    !isUser &&
    !streaming &&
    !message.error &&
    Boolean(message.serverId) &&
    message.content.trim().length > 0;

  async function submitFeedback(rating: 1 | -1) {
    if (!message.serverId || savingFeedback || message.feedback != null) return;
    setSavingFeedback(true);
    try {
      await sendChatFeedback(message.serverId, rating);
      useChatStore.getState().patchMessage(message.id, { feedback: rating });
      useToastStore.getState().push(t("chat.feedbackThanks"));
    } catch (err) {
      const raw = err instanceof Error ? err.message : t("errors.feedbackFailed");
      const text =
        err instanceof ApiRequestError ? userFacingApiMessage(err.status, err.message) : raw;
      useToastStore.getState().push(text);
    } finally {
      setSavingFeedback(false);
    }
  }

  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[min(92%,36rem)] min-w-0 rounded-2xl px-3 py-2.5 text-sm leading-relaxed sm:px-4 sm:py-3",
          isUser ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-100",
          message.error ? "border border-red-500/40" : "",
        )}
      >
        {!isUser ? (
          <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-slate-500">
            Docwise{message.cached ? t("chat.cachedSuffix") : ""}
          </p>
        ) : null}
        {chips.length > 0 ? (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {chips.map((citation) => (
              <CitationTag
                key={`${citation.doc_id}:${citation.page}`}
                citation={citation}
                onSelect={onSelectCitation}
              />
            ))}
          </div>
        ) : null}
        <div className="break-words">
          {message.content ? (
            isUser ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : isRefusal ? (
              <Alert variant="warning" className="border-0 bg-transparent px-0 py-0 text-amber-200">
                {message.content}
              </Alert>
            ) : message.error ? (
              <Alert variant="destructive" className="border-0 bg-transparent px-0 py-0">
                {message.content}
              </Alert>
            ) : chips.length > 0 ? (
              <AnswerMarkdown text={plainContent} className="block [&_p]:my-0" />
            ) : (
              parts.map((part, index) =>
                part.type === "text" ? (
                  <AnswerMarkdown key={index} text={part.value} className="block [&_p]:my-0" />
                ) : (
                  <CitationTag
                    key={`${part.citation.doc_id}:${part.citation.page}:${index}`}
                    citation={part.citation}
                    onSelect={onSelectCitation}
                    className="ml-1 align-middle"
                  />
                ),
              )
            )
          ) : streaming ? (
            t("chat.typing")
          ) : null}
          {streaming && message.content ? (
            <span className="ml-0.5 inline-block h-3 w-1 animate-pulse bg-current align-middle" />
          ) : null}
        </div>
        {canFeedback ? (
          <div className="mt-2 flex items-center gap-1 border-t border-slate-700/80 pt-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className={cn(
                "h-7 gap-1.5 px-2 text-xs text-slate-400 hover:text-slate-100",
                message.feedback === 1 && "text-emerald-400 hover:text-emerald-300",
              )}
              disabled={savingFeedback || message.feedback != null}
              aria-label={t("chat.feedbackUseful")}
              aria-pressed={message.feedback === 1}
              onClick={() => void submitFeedback(1)}
            >
              <ThumbsUp className="size-3.5" aria-hidden />
              {t("chat.feedbackUseful")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className={cn(
                "h-7 gap-1.5 px-2 text-xs text-slate-400 hover:text-slate-100",
                message.feedback === -1 && "text-amber-400 hover:text-amber-300",
              )}
              disabled={savingFeedback || message.feedback != null}
              aria-label={t("chat.feedbackNotUseful")}
              aria-pressed={message.feedback === -1}
              onClick={() => void submitFeedback(-1)}
            >
              <ThumbsDown className="size-3.5" aria-hidden />
              {t("chat.feedbackNotUseful")}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
