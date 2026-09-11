"use client";

import { useEffect, useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FadeIn } from "@/components/ui/fade-in";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchHealth } from "@/lib/api";
import type { HealthResponse } from "@/types/health";

const CHECKS = ["postgres", "redis", "pgvector", "minio", "billing"] as const;

function checkOk(key: (typeof CHECKS)[number], value: string): boolean {
  if (key === "billing") return value === "ok" || value === "dev";
  return value === "ok";
}

function StatusBadge({ value, ok }: { value: string; ok: boolean }) {
  return <Badge variant={ok ? (value === "dev" ? "warning" : "success") : "destructive"}>{value}</Badge>;
}

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card>
        <CardContent className="space-y-2">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-48" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">Не удалось подключиться к API: {error}</Alert>
    );
  }

  if (!health) return null;

  const allOk = health.status === "ok";

  return (
    <FadeIn>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium text-slate-400">Backend status</CardTitle>
          <StatusBadge value={health.status} ok={allOk} />
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-lg font-semibold capitalize">{health.status}</p>
          <ul className="space-y-2">
            {CHECKS.map((key) => (
              <li key={key} className="flex items-center justify-between text-sm">
                <span className="text-slate-400">{key}</span>
                <StatusBadge value={health[key]} ok={checkOk(key, health[key])} />
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-slate-500">env: {health.environment}</p>
        </CardContent>
      </Card>
    </FadeIn>
  );
}
