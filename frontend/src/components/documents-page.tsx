"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGate } from "@/components/auth-gate";
import { Badge } from "@/components/ui/badge";
import { ApiRequestError, fetchDocuments } from "@/lib/api";
import { formatBytes, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS_VARIANT: Record<string, "secondary" | "success" | "warning" | "destructive"> = {
  pending: "warning",
  processing: "warning",
  ready: "success",
  failed: "destructive",
};

export function DocumentsPage() {
  const query = useQuery({
    queryKey: ["documents"],
    queryFn: () => fetchDocuments(50, 0),
  });

  return (
    <AuthGate>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-xl font-semibold">База знаний</h2>
            <p className="mt-1 text-sm text-slate-400">
              Документы, которые вам доступны. Загрузка и роли — в следующем шаге этой вехи.
            </p>
          </div>
          {query.isLoading ? (
            <p className="text-sm text-slate-400">Загрузка…</p>
          ) : null}
          {query.error ? (
            <p className="text-sm text-red-400">
              {query.error instanceof ApiRequestError
                ? query.error.message
                : "Не удалось загрузить документы"}
            </p>
          ) : null}
          {query.data && query.data.items.length === 0 ? (
            <p className="text-sm text-slate-400">Пока нет документов, которые вам видно.</p>
          ) : null}
          {query.data && query.data.items.length > 0 ? (
            <div className="overflow-x-auto rounded-xl border border-slate-800">
              <table className="w-full min-w-[40rem] text-left text-sm">
                <thead className="border-b border-slate-800 bg-slate-900/70 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">Название</th>
                    <th className="px-3 py-2 font-medium">Размер</th>
                    <th className="px-3 py-2 font-medium">Страницы</th>
                    <th className="px-3 py-2 font-medium">Доступ</th>
                    <th className="px-3 py-2 font-medium">Статус</th>
                    <th className="px-3 py-2 font-medium">Дата</th>
                  </tr>
                </thead>
                <tbody>
                  {query.data.items.map((doc) => (
                    <tr key={doc.id} className="border-b border-slate-800/80 last:border-0">
                      <td className="px-3 py-2 text-slate-100">{doc.title}</td>
                      <td className="px-3 py-2 text-slate-400">{formatBytes(doc.file_size_bytes)}</td>
                      <td className="px-3 py-2 text-slate-400">{doc.total_pages ?? "—"}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap gap-1">
                          {doc.access_roles.map((role) => (
                            <Badge key={role} variant="outline">
                              {role}
                            </Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={STATUS_VARIANT[doc.status] ?? "secondary"}>{doc.status}</Badge>
                      </td>
                      <td className={cn("px-3 py-2 text-slate-400")}>
                        {formatDateTime(doc.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </main>
    </AuthGate>
  );
}
