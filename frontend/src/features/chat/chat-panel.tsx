"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowUp, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { useAuth } from "@/features/auth/auth-provider";
import { ChatMessageBubble } from "@/features/chat/chat-message-bubble";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, fetchChatSession, streamChat } from "@/lib/api";
import { uniqueCitations } from "@/features/chat/lib/chat";
import { ChatEmptyState } from "@/features/chat/chat-empty-state";
import { takePendingQuestion } from "@/features/chat/lib/pending-question";
import {
  hasSeenCitationHint,
  markCitationHintSeen,
} from "@/features/chat/lib/citation-hint";
import { useI18n } from "@/i18n/locale-provider";
import { userFacingChatError } from "@/lib/chat-errors";
import { canManageOrganization } from "@/lib/access-roles";
import { useChatStore, type UiMessage } from "@/features/chat/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import type { ChatStreamEvent, Citation } from "@/types/chat";

export function ChatPanel({
  sessionId,
  onSelectCitation,
}: {
  sessionId?: string | null;
  onSelectCitation?: (citation: Citation) => void;
}) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const user = useAuth().user;
  const userId = user?.id;
  const [question, setQuestion] = useState("");
  const [showCitationHint, setShowCitationHint] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(Boolean(sessionId));
  const messages = useChatStore((state) => state.messages);
  const sending = useChatStore((state) => state.sending);
  const listRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { t } = useI18n();

  function resizeInput() {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }

  useEffect(() => {
    let cancelled = false;
    const store = useChatStore.getState();

    if (!sessionId) {
      if (store.sending || store.sessionId) {
        setLoadingHistory(false);
        return;
      }
      if (store.loadedFor === "") {
        setLoadingHistory(false);
        return;
      }
      store.resetNew();
      setLoadingHistory(false);
      return;
    }

    if (store.loadedFor === sessionId && store.messages.length > 0) {
      setLoadingHistory(false);
      return;
    }

    setLoadingHistory(true);
    void fetchChatSession(sessionId)
      .then((detail) => {
        if (cancelled) return;
        useChatStore.getState().hydrate(
          sessionId,
          detail.messages.map((item) => ({
            id: item.id,
            role: item.role,
            content: item.content,
            sources: item.sources ?? [],
            created_at: item.created_at,
            serverId: item.role === "assistant" ? item.id : null,
          })),
        );
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiRequestError && (err.status === 404 || err.status === 403)) {
          useChatStore.getState().resetNew();
          router.replace("/");
          return;
        }
        const message = t("errors.loadChatHistoryFailed");
        useToastStore.getState().push(message);
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId, userId, router]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const pending = takePendingQuestion();
    if (pending) {
      setQuestion(pending);
      requestAnimationFrame(() => resizeInput());
    }
  }, []);

  useEffect(() => {
    if (hasSeenCitationHint()) return;
    const hasCitation = messages.some(
      (item) => item.role === "assistant" && uniqueCitations(item.sources).length > 0,
    );
    setShowCitationHint(hasCitation);
  }, [messages]);

  function chatErrorMessage(status: number | undefined, raw: string): string {
    const showDevLlmHint =
      process.env.NODE_ENV === "development" || canManageOrganization(user);
    const localized = userFacingChatError(status, raw, { showDevLlmHint });
    return localized === raw ? t("errors.chatReplyFailed") : localized;
  }

  async function send(text: string) {
    const trimmed = text.trim();
    const store = useChatStore.getState();
    if (!trimmed || store.sending || loadingHistory) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const userMessage: UiMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: trimmed,
      sources: [],
      created_at: new Date().toISOString(),
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMessage: UiMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      sources: [],
      created_at: new Date().toISOString(),
    };

    setQuestion("");
    store.appendMessages([userMessage, assistantMessage]);
    store.setSending(true);
    requestAnimationFrame(() => {
      if (inputRef.current) inputRef.current.style.height = "auto";
    });

    const applyEvent = (event: ChatStreamEvent) => {
      const chat = useChatStore.getState();
      if (event.type === "token") {
        chat.patchMessage(assistantId, (item) => ({
          ...item,
          content: item.content + event.content,
        }));
        return;
      }
      if (event.type === "citations") {
        chat.patchMessage(assistantId, { sources: event.citations });
        return;
      }
      if (event.type === "meta") {
        if (event.session_id) {
          const isNewSession = chat.sessionId !== event.session_id;
          chat.setSessionId(event.session_id);
          const path = `/chat/${event.session_id}`;
          if (window.location.pathname !== path) {
            window.history.replaceState(window.history.state, "", path);
          }
          if (isNewSession) {
            void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
          }
        }
        chat.patchMessage(assistantId, {
          cached: event.cached,
          serverId: event.message_id ?? undefined,
        });
        return;
      }
      if (event.type === "error") {
        const message = chatErrorMessage(undefined, event.content);
        useToastStore.getState().push(message);
        chat.patchMessage(assistantId, (item) => {
          if (item.content.trim()) return item;
          return { ...item, content: message, error: true };
        });
      }
    };

    try {
      await streamChat(trimmed, applyEvent, {
        sessionId: useChatStore.getState().sessionId || sessionId || null,
        signal: controller.signal,
      });
    } catch (err) {
      if (controller.signal.aborted) return;
      const message =
        err instanceof ApiRequestError
          ? chatErrorMessage(err.status, err.message)
          : err instanceof Error
            ? chatErrorMessage(undefined, err.message)
            : t("errors.chatReplyFailed");
      useToastStore.getState().push(message);
      useChatStore.getState().patchMessage(assistantId, (item) => ({
        ...item,
        content: item.content || message,
        error: true,
      }));
    } finally {
      useChatStore.getState().setSending(false);
    }
  }

  function handleSelectCitation(citation: Citation) {
    markCitationHintSeen();
    setShowCitationHint(false);
    onSelectCitation?.(citation);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;
    const isCoarse = window.matchMedia("(pointer: coarse)").matches;
    if (isCoarse) return;
    event.preventDefault();
    void send(question);
  }

  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-4 sm:py-5">
        <div className="mx-auto flex min-h-full min-w-0 max-w-2xl flex-col gap-4 sm:gap-5">
          {loadingHistory ? (
            <div className="flex flex-1 flex-col justify-center gap-3 py-10">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-5/6 self-end" />
              <Skeleton className="h-24 w-full" />
            </div>
          ) : messages.length === 0 ? (
            <ChatEmptyState onSend={(text) => void send(text)} />
          ) : (
            messages.map((message) => (
              <ChatMessageBubble
                key={message.id}
                message={message}
                streaming={sending && message.role === "assistant" && !message.error}
                onSelectCitation={handleSelectCitation}
              />
            ))
          )}
        </div>
      </div>

      {showCitationHint ? (
        <div className="shrink-0 border-t border-slate-800 bg-slate-950/80 px-3 py-2 sm:px-4">
          <div className="mx-auto flex max-w-2xl items-start justify-between gap-2">
            <Alert className="flex-1 py-2 text-left text-xs sm:text-sm">{t("chat.citationClickHint")}</Alert>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="shrink-0 text-xs"
              onClick={() => {
                markCitationHintSeen();
                setShowCitationHint(false);
              }}
            >
              {t("common.close")}
            </Button>
          </div>
        </div>
      ) : null}

      <div className="shrink-0 border-t border-slate-800 bg-slate-950 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-4 sm:py-4">
        <div className="mx-auto min-w-0 max-w-2xl">
          <div className="flex min-w-0 items-center gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-2 py-1.5 sm:py-2">
            <Textarea
              ref={inputRef}
              value={question}
              onChange={(event) => {
                setQuestion(event.target.value);
                resizeInput();
              }}
              onKeyDown={handleKeyDown}
              placeholder={t("chat.placeholder")}
              disabled={sending || loadingHistory}
              rows={1}
              className="max-h-32 min-h-11 min-w-0 flex-1 resize-none overflow-y-auto rounded-xl border-0 bg-transparent sm:max-h-40"
            />
            <Button
              type="button"
              size="icon"
              className="size-10 shrink-0 sm:size-9"
              disabled={sending || loadingHistory || !question.trim()}
              onClick={() => void send(question)}
              aria-label={t("chat.send")}
            >
              {sending ? <LoaderCircle className="animate-spin" /> : <ArrowUp />}
            </Button>
          </div>
          <p className="mt-2 hidden text-center text-[11px] text-slate-500 sm:block">
            {t("chat.inputHint")}
          </p>
        </div>
      </div>
    </div>
  );
}
