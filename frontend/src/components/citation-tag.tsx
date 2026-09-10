"use client";

import { citationLabel } from "@/lib/chat";
import { cn } from "@/lib/utils";
import type { Citation } from "@/types/chat";

export function CitationTag({
  citation,
  onSelect,
  className,
}: {
  citation: Citation;
  onSelect?: (citation: Citation) => void;
  className?: string;
}) {
  const label = citationLabel(citation);
  return (
    <button
      type="button"
      onClick={() => onSelect?.(citation)}
      onKeyDown={(event) => {
        if (event.key !== "Enter" && event.key !== " ") return;
        event.preventDefault();
        onSelect?.(citation);
      }}
      title={citation.snippet}
      className={cn(
        "inline-flex max-w-full items-center truncate rounded-full border border-blue-500/40 bg-blue-500/15 px-2 py-0.5 text-left text-[11px] font-medium text-blue-200",
        "hover:bg-blue-500/25 focus-visible:ring-2 focus-visible:ring-blue-500/60",
        className,
      )}
    >
      {label}
    </button>
  );
}
