"use client";

import { FormEvent, useState } from "react";

import { AuthGate } from "@/features/auth/auth-gate";
import { useAuth } from "@/features/auth/auth-provider";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { FadeIn } from "@/components/ui/fade-in";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/i18n/locale-provider";
import { canManageOrganization } from "@/lib/access-roles";
import { inspectSearch } from "@/lib/api";
import { inspectErrorMessage } from "@/features/inspect/inspect-error";
import { INSPECT_STAGES, type InspectHit, type InspectStage, type SearchInspectResponse } from "@/types/search";

const STAGE_HINT: Record<InspectStage, string> = {
  dense: "pgvector cosine Top-N",
  sparse: "Postgres FTS Top-N",
  rrf: "reciprocal rank fusion k=60",
  reranked: "cross-encoder, then threshold",
};

export function InspectPage() {
  const { t } = useI18n();
  const { user } = useAuth();
  const isAdmin = canManageOrganization(user);
  const [query, setQuery] = useState("What is the individual contributor L3 salary band in USD?");
  const [limit, setLimit] = useState(15);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SearchInspectResponse | null>(null);
  const [stage, setStage] = useState<InspectStage>("reranked");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!isAdmin) return;
    setSubmitting(true);
    setError(null);
    try {
      const payload = await inspectSearch(query, limit);
      setResult(payload);
    } catch (err) {
      setResult(null);
      setError(inspectErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthGate>
      <main className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <FadeIn className="mx-auto max-w-5xl space-y-4">
          <div>
            <h2 className="text-xl font-semibold">{t("inspect.title")}</h2>
            <p className="mt-1 text-sm text-slate-400">{t("inspect.intro")}</p>
          </div>
          {!isAdmin ? (
            <Alert variant="destructive">{t("errors.inspectForbidden")}</Alert>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-3 rounded-xl border border-slate-800 p-4">
              <div>
                <Label htmlFor="inspect-query">{t("inspect.query")}</Label>
                <Input
                  id="inspect-query"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  required
                  maxLength={4000}
                />
              </div>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <div className="w-full sm:w-28">
                  <Label htmlFor="inspect-limit">{t("inspect.limit")}</Label>
                  <Input
                    id="inspect-limit"
                    type="number"
                    min={1}
                    max={50}
                    value={limit}
                    onChange={(event) => setLimit(Number(event.target.value))}
                    className="mt-1 w-full"
                  />
                </div>
                <Button
                  type="submit"
                  className="w-full sm:w-auto"
                  disabled={submitting || !query.trim()}
                >
                  {submitting ? "…" : t("inspect.run")}
                </Button>
              </div>
            </form>
          )}
          {error ? <Alert variant="destructive">{error}</Alert> : null}
          {result ? (
            <InspectResults result={result} stage={stage} onStage={setStage} emptyHits={t("inspect.emptyHits")} colPage={t("inspect.colPage")} />
          ) : null}
        </FadeIn>
      </main>
    </AuthGate>
  );
}

function InspectResults({
  result,
  stage,
  onStage,
  emptyHits,
  colPage,
}: {
  result: SearchInspectResponse;
  stage: InspectStage;
  onStage: (value: InspectStage) => void;
  emptyHits: string;
  colPage: string;
}) {
  return (
    <Tabs value={stage} onValueChange={(value) => onStage(value as InspectStage)}>
      <TabsList className="grid-cols-2 lg:grid-cols-4">
        {INSPECT_STAGES.map((item) => (
          <TabsTrigger key={item} value={item} className="h-10 px-2 text-xs sm:text-sm">
            {item} ({result[item].length})
          </TabsTrigger>
        ))}
      </TabsList>
      {INSPECT_STAGES.map((item) => (
        <TabsContent key={item} value={item} className="space-y-2">
          <p className="text-xs text-slate-500">{STAGE_HINT[item]}</p>
          <HitTable hits={result[item]} emptyHits={emptyHits} colPage={colPage} />
        </TabsContent>
      ))}
    </Tabs>
  );
}

function HitTable({
  hits,
  emptyHits,
  colPage,
}: {
  hits: InspectHit[];
  emptyHits: string;
  colPage: string;
}) {
  const { t } = useI18n();
  if (hits.length === 0) {
    return <Alert>{emptyHits}</Alert>;
  }
  return (
    <>
      <div className="space-y-3 lg:hidden">
        {hits.map((hit) => (
          <article
            key={hit.chunk_id}
            className="min-w-0 rounded-xl border border-slate-800 bg-slate-950/40 p-3"
          >
            <div className="mb-2 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <span className="block text-[10px] font-medium uppercase tracking-wide text-slate-500">
                  {t("inspect.colScore")}
                </span>
                <span className="font-mono text-sm text-slate-100">{hit.score.toFixed(3)}</span>
              </div>
              <div className="shrink-0 text-right">
                <span className="block text-[10px] font-medium uppercase tracking-wide text-slate-500">
                  {colPage}
                </span>
                <span className="text-sm text-slate-200">{hit.page}</span>
              </div>
            </div>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-slate-300">
              {hit.snippet}
            </p>
            <details className="mt-3 border-t border-slate-800 pt-2">
              <summary className="cursor-pointer py-1 text-xs text-slate-400">
                {t("inspect.colChunkId")}
              </summary>
              <code className="mt-1 block break-all text-[11px] text-slate-500">{hit.chunk_id}</code>
            </details>
          </article>
        ))}
      </div>
      <div className="hidden rounded-xl border border-slate-800 lg:block">
        <Table className="min-w-[56rem]">
          <TableHeader>
            <TableRow>
              <TableHead>{t("inspect.colScore")}</TableHead>
              <TableHead>{colPage}</TableHead>
              <TableHead>{t("inspect.colSnippet")}</TableHead>
              <TableHead>{t("inspect.colChunkId")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
          {hits.map((hit) => (
            <TableRow key={hit.chunk_id}>
              <TableCell className="font-mono text-xs">{hit.score.toFixed(3)}</TableCell>
              <TableCell>{hit.page}</TableCell>
              <TableCell className="max-w-md break-words text-slate-300">{hit.snippet}</TableCell>
              <TableCell className="max-w-[12rem] break-all font-mono text-[11px] text-slate-500">
                {hit.chunk_id}
              </TableCell>
            </TableRow>
          ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}
