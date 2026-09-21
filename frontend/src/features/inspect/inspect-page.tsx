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
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <Label htmlFor="inspect-limit">{t("inspect.limit")}</Label>
                  <Input
                    id="inspect-limit"
                    type="number"
                    min={1}
                    max={50}
                    value={limit}
                    onChange={(event) => setLimit(Number(event.target.value))}
                    className="w-24"
                  />
                </div>
                <Button type="submit" disabled={submitting || !query.trim()}>
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
      <TabsList className="grid-cols-2 sm:grid-cols-4">
        {INSPECT_STAGES.map((item) => (
          <TabsTrigger key={item} value={item}>
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
  if (hits.length === 0) {
    return <Alert>{emptyHits}</Alert>;
  }
  return (
    <div className="rounded-xl border border-slate-800">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Score</TableHead>
            <TableHead>{colPage}</TableHead>
            <TableHead>Snippet</TableHead>
            <TableHead>chunk_id</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {hits.map((hit) => (
            <TableRow key={hit.chunk_id}>
              <TableCell className="font-mono text-xs">{hit.score.toFixed(3)}</TableCell>
              <TableCell>{hit.page}</TableCell>
              <TableCell className="max-w-md text-slate-300">{hit.snippet}</TableCell>
              <TableCell className="max-w-[12rem] truncate font-mono text-[11px] text-slate-500">
                {hit.chunk_id}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
