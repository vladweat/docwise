"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus, PanelLeftClose } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { ApiRequestError, fetchChatSessions } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { useViewerStore } from "@/stores/viewer-store";

export function ChatSessionList({
  currentId,
  onClose,
}: {
  currentId?: string | null;
  onClose?: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const storeSessionId = useChatStore((state) => state.sessionId);
  const activeId = currentId || storeSessionId;
  const pushToast = useToastStore((state) => state.push);

  const { user } = useAuth();
  const query = useQuery({
    queryKey: ["chat-sessions", user?.id],
    queryFn: () => fetchChatSessions(50, 0),
    enabled: Boolean(user),
  });

  const sidebar = Boolean(onClose);

  function startNew() {
    useChatStore.getState().resetNew();
    useViewerStore.getState().clear();
    void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    router.push("/");
  }

  const header = (
    <div className="flex items-center gap-1 px-2 py-2">
      <p className="min-w-0 flex-1 px-1 text-xs font-medium uppercase tracking-wide text-slate-500">
        Сессии
      </p>
      <Button type="button" variant="ghost" size="sm" className="h-8 px-2" onClick={startNew}>
        <MessageSquarePlus />
        <span className="hidden sm:inline">Новая</span>
      </Button>
      {onClose ? (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="size-8 shrink-0"
          onClick={onClose}
          aria-label="Скрыть список сессий"
          title="Скрыть список сессий"
        >
          <PanelLeftClose />
        </Button>
      ) : null}
    </div>
  );

  if (query.error && !query.data) {
    const message =
      query.error instanceof ApiRequestError
        ? query.error.message
        : "Не удалось загрузить сессии";
    return (
      <aside className={sessionAsideClass(sidebar)}>
        {header}
        <p className="px-3 pb-3 text-xs text-red-400">{message}</p>
      </aside>
    );
  }

  const items = query.data?.items ?? [];

  return (
    <aside className={sessionAsideClass(sidebar)}>
      {header}
      <ul
        className={cn(
          "flex min-h-0 flex-1 gap-1 overflow-x-auto px-2 pb-2",
          sidebar
            ? "flex-col overflow-y-auto overflow-x-hidden pb-3"
            : "md:flex-col md:overflow-y-auto md:overflow-x-hidden md:pb-3",
        )}
      >
        {query.isLoading ? (
          <li className="px-2 py-2 text-xs text-slate-500">Загрузка…</li>
        ) : items.length === 0 ? (
          <li className="px-2 py-2 text-xs text-slate-500">Пока пусто</li>
        ) : (
          items.map((item) => {
            const active = item.id === activeId;
            return (
              <li key={item.id} className="shrink-0 md:shrink">
                <Link
                  href={`/chat/${item.id}`}
                  className={cn(
                    "block max-w-[14rem] truncate rounded-lg px-2 py-1.5 text-left text-sm md:max-w-none",
                    active
                      ? "bg-slate-800 text-slate-100"
                      : "text-slate-300 hover:bg-slate-900",
                  )}
                  title={item.title ?? "Без названия"}
                >
                  <span className="block truncate">{item.title || "Без названия"}</span>
                  <span
                    className={cn(
                      "text-[10px] text-slate-500",
                      sidebar ? "block" : "hidden md:block",
                    )}
                  >
                    {formatDateTime(item.updated_at)}
                  </span>
                </Link>
              </li>
            );
          })
        )}
      </ul>
      {query.isError ? (
        <button
          type="button"
          className="px-3 pb-2 text-left text-[11px] text-red-400 hover:underline"
          onClick={() => {
            pushToast(
              query.error instanceof ApiRequestError
                ? query.error.message
                : "Не удалось загрузить сессии",
            );
            void query.refetch();
          }}
        >
          Повторить загрузку
        </button>
      ) : null}
    </aside>
  );
}

function sessionAsideClass(sidebar: boolean) {
  return sidebar
    ? "flex h-full w-52 shrink-0 flex-col border-r border-slate-800 bg-slate-950"
    : "flex max-h-28 w-full shrink-0 flex-col border-b border-slate-800 md:max-h-none md:w-52 md:border-b-0 md:border-r";
}
