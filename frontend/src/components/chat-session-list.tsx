"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { ApiRequestError, fetchChatSessions } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useChatStore } from "@/stores/chat-store";
import { useToastStore } from "@/stores/toast-store";
import { useViewerStore } from "@/stores/viewer-store";

export function ChatSessionList({ currentId }: { currentId?: string | null }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const storeSessionId = useChatStore((state) => state.sessionId);
  const activeId = currentId || storeSessionId;
  const pushToast = useToastStore((state) => state.push);

  const query = useQuery({
    queryKey: ["chat-sessions"],
    queryFn: () => fetchChatSessions(50, 0),
  });

  if (query.error && !query.data) {
    const message =
      query.error instanceof ApiRequestError
        ? query.error.message
        : "Не удалось загрузить сессии";
    return (
      <aside className="flex w-full shrink-0 flex-col border-b border-slate-800 md:w-52 md:border-b-0 md:border-r">
        <p className="px-3 py-3 text-xs text-red-400">{message}</p>
      </aside>
    );
  }

  const items = query.data?.items ?? [];

  function startNew() {
    useChatStore.getState().resetNew();
    useViewerStore.getState().clear();
    void queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    router.push("/");
  }

  return (
    <aside className="flex max-h-28 w-full shrink-0 flex-col border-b border-slate-800 md:max-h-none md:w-52 md:border-b-0 md:border-r">
      <div className="flex items-center justify-between gap-2 px-2 py-2">
        <p className="px-1 text-xs font-medium uppercase tracking-wide text-slate-500">Сессии</p>
        <Button type="button" variant="ghost" size="sm" className="h-8 px-2" onClick={startNew}>
          <MessageSquarePlus />
          <span className="hidden sm:inline">Новая</span>
        </Button>
      </div>
      <ul className="flex min-h-0 flex-1 gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:overflow-y-auto md:overflow-x-hidden md:pb-3">
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
                  <span className="hidden text-[10px] text-slate-500 md:block">
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
