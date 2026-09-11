"use client";

import { PanelLeftOpen, PanelRightOpen } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function PaneRail({
  side,
  label,
  onClick,
}: {
  side: "left" | "right";
  label: string;
  onClick: () => void;
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className={cn(
        "h-auto w-9 shrink-0 rounded-none text-slate-400 hover:bg-slate-900 hover:text-slate-100",
        side === "left" ? "border-r border-slate-800" : "border-l border-slate-800",
      )}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      {side === "left" ? <PanelLeftOpen /> : <PanelRightOpen />}
    </Button>
  );
}
