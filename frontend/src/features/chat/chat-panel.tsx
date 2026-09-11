"use client";

import { useQueryClient } from "@tanstack/react-query";
import { ArrowUp, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { useAuth } from "@/features/auth/auth-provider";
import { AnswerMarkdown } from "@/features/chat/answer-markdown";
import { CitationTag } from "@/features/chat/citation-tag";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { ApiRequestError, fetchChatSession, streamChat } from "@/lib/api";
import { NO_CONTEXT_ANSWER, splitAnswerParts, uniqueCitations } from "@/features/chat/lib/chat";
import { userFacingApiMessage } from "@/lib/quota";
import { cn } from "@/lib/utils";
import { useChatStore, type UiMessage } from "@/features/chat/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import type { ChatStreamEvent, Citation } from "@/types/chat";

const SUGGESTIONS = [
  "Какой суточный лимит компенсации командировок?",
  "Какие документы нужны для отпуска?",
  "Где описана политика удалённой работы?",
];

export function ChatPanel({
  sessionId,
  onSelectCitation,
}: {
  sessionId?: string | null;
  onSelectCitation?: (citation: Citation) => void;
}) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const userId = useAuth().user?.id;
  const [question, setQuestion] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(Boolean(sessionId));
  const messages = useChatStore((state) => state.messages);
  const sending = useChatStore((state) => state.sending);
  const listRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
        const message =
          err instanceof ApiRequestError
            ? err.message
            : "Не удалось загрузить историю чата";
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
          chat.setSessionId(event.session_id);
          const path = `/chat/${event.session_id}`;
          if (window.location.pathname !== path) {
            window.history.replaceState(window.history.state, "", path);
          }
          void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        }
        chat.patchMessage(assistantId, {
          cached: event.cached,
          serverId: event.message_id ?? undefined,
        });
        return;
      }
      if (event.type === "error") {
        const message = userFacingApiMessage(undefined, event.content);
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
          ? userFacingApiMessage(err.status, err.message)
          : err instanceof Error
            ? err.message
            : "Не удалось получить ответ";
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
            <div className="flex flex-1 flex-col items-center justify-center gap-5 py-6 text-center sm:py-10">
              <div>
                <h2 className="text-lg font-semibold sm:text-xl">Спросите по документам</h2>
                <p className="mt-2 max-w-md text-sm text-slate-400">
                  Ответ строится только по файлам, которые вам доступны. Каждая цитата ведёт на
                  страницу PDF.
                </p>
              </div>
              <div className="flex w-full flex-col gap-2">
                {SUGGESTIONS.map((item) => (
                  <Button
                    key={item}
                    type="button"
                    variant="outline"
                    onClick={() => void send(item)}
                    className="h-auto justify-start whitespace-normal rounded-xl px-4 py-3 text-left font-normal"
                  >
                    {item}
                  </Button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                streaming={sending && message.role === "assistant" && !message.error}
                onSelectCitation={onSelectCitation}
              />
            ))
          )}
        </div>
      </div>

      <div className="shrink-0 border-t border-slate-800 bg-slate-950 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 sm:px-4 sm:py-4">
        <div className="mx-auto min-w-0 max-w-2xl">
          <div className="flex min-w-0 items-end gap-2 rounded-2xl border border-slate-700 bg-slate-900 px-2 py-2">
            <Textarea
              ref={inputRef}
              value={question}
              onChange={(event) => {
                setQuestion(event.target.value);
                resizeInput();
              }}
              onKeyDown={handleKeyDown}
              placeholder="Вопрос по корпоративным документам…"
              disabled={sending || loadingHistory}
              rows={1}
              className="max-h-32 min-h-11 min-w-0 flex-1 resize-none overflow-y-auto rounded-xl border-0 bg-transparent sm:max-h-40"
            />
            <Button
              type="button"
              size="icon"
              className="mb-0.5 size-11 shrink-0 sm:size-9"
              disabled={sending || loadingHistory || !question.trim()}
              onClick={() => void send(question)}
              aria-label="Отправить"
            >
              {sending ? <LoaderCircle className="animate-spin" /> : <ArrowUp />}
            </Button>
          </div>
          <p className="mt-2 hidden text-center text-[11px] text-slate-500 sm:block">
            Enter — отправить, Shift+Enter — новая строка
          </p>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  streaming,
  onSelectCitation,
}: {
  message: UiMessage;
  streaming: boolean;
  onSelectCitation?: (citation: Citation) => void;
}) {
  const isUser = message.role === "user";
  const chips = uniqueCitations(message.sources);
  const parts = splitAnswerParts(message.content, message.sources);
  const isRefusal = message.content.trim() === NO_CONTEXT_ANSWER;

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
            Docwise{message.cached ? " · из кеша" : ""}
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
            isUser || isRefusal ? (
              <span className="whitespace-pre-wrap">{message.content}</span>
            ) : (
              parts.map((part, index) =>
                part.type === "text" ? (
                  <AnswerMarkdown key={index} text={part.value} className="inline-block w-full" />
                ) : (
                  <CitationTag
                    key={`${part.citation.doc_id}:${part.citation.page}:${index}`}
                    citation={part.citation}
                    onSelect={onSelectCitation}
                    className="mx-0.5 align-middle"
                  />
                ),
              )
            )
          ) : streaming ? (
            "Печатает…"
          ) : null}
          {streaming && message.content ? (
            <span className="ml-0.5 inline-block h-3 w-1 animate-pulse bg-current align-middle" />
          ) : null}
        </div>
      </div>
    </div>
  );
}
