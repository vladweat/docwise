import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex min-h-16 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-base text-slate-100 outline-none transition-colors placeholder:text-slate-500 focus:border-blue-500 disabled:opacity-50 sm:text-sm",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
