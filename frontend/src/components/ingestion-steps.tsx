"use client";

import { INGESTION_STEPS, type IngestionStep } from "@/types/document";
import { cn } from "@/lib/utils";

const LABELS: Record<IngestionStep, string> = {
  parse: "parse",
  chunk: "chunk",
  embed: "embed",
};

function stepIndex(stage: string | null | undefined): number {
  if (!stage) return -1;
  return INGESTION_STEPS.indexOf(stage as IngestionStep);
}

export function IngestionSteps({
  status,
  stage,
}: {
  status: string;
  stage: string | null | undefined;
}) {
  const current = stepIndex(stage);
  const failed = status === "failed";
  const ready = status === "ready";
  const pending = status === "pending";

  return (
    <ol className="mt-1 flex flex-wrap items-center gap-1 text-[11px] text-slate-500" aria-label="Шаги обработки">
      {INGESTION_STEPS.map((step, index) => {
        const isDone = ready || (!failed && !pending && current > index);
        const isActive = !ready && !failed && !pending && current === index;
        const isFailedStep = failed && (current === index || (current < 0 && index === 0));
        return (
          <li key={step} className="flex items-center gap-1">
            {index > 0 ? <span className="text-slate-700">→</span> : null}
            <span
              className={cn(
                "rounded px-1 py-0.5 font-medium",
                isDone && "bg-emerald-500/15 text-emerald-400",
                isActive && "bg-amber-500/20 text-amber-300",
                isFailedStep && "bg-red-500/20 text-red-400",
                !isDone && !isActive && !isFailedStep && "text-slate-600",
              )}
            >
              {LABELS[step]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
