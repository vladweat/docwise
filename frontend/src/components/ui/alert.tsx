import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva("relative w-full rounded-lg border px-3 py-2 text-sm", {
  variants: {
    variant: {
      default: "border-slate-800 bg-slate-900/60 text-slate-200",
      destructive: "border-red-900/50 bg-red-950/40 text-red-400",
      warning: "border-amber-900/40 bg-amber-950/30 text-amber-300",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  );
}

function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="alert-title" className={cn("font-medium", className)} {...props} />;
}

function AlertDescription({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="alert-description" className={cn("text-sm", className)} {...props} />;
}

export { Alert, AlertDescription, AlertTitle };
