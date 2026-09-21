"use client";

import { AnswerMarkdown } from "@/features/chat/answer-markdown";
import { CitationTag } from "@/features/chat/citation-tag";
import {
  isNoContextAnswer,
  splitAnswerParts,
  stripCitationMarkers,
  uniqueCitations,
} from "@/features/chat/lib/chat";
import { Alert } from "@/components/ui/alert";
import { useI18n } from "@/i18n/locale-provider";
import { cn } from "@/lib/utils";
import type { UiMessage } from "@/features/chat/stores/chat-store";
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
  const isUser = message.role === "user";
  const chips = uniqueCitations(message.sources);
  const parts = splitAnswerParts(message.content, message.sources);
  const plainContent = chips.length > 0 ? stripCitationMarkers(message.content) : message.content;
  const isRefusal = isNoContextAnswer(message.content);

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
      </div>
    </div>
  );
}
