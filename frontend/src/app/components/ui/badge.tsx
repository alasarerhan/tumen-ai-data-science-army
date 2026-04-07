import React from "react";
import { cn } from "../../lib/utils";
import type { RunStatus } from "../../api/runs";

type BadgeVariant = "neutral" | "indigo" | "success" | "warning" | "danger" | "info" | "violet";

interface BadgeProps {
  variant?: BadgeVariant;
  size?: "sm" | "md";
  dot?: boolean;
  pulsing?: boolean;
  children: React.ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  neutral: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
  indigo: "bg-indigo-50 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
  success: "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
  danger: "bg-red-50 text-red-700 dark:bg-red-900/40 dark:text-red-400",
  info: "bg-sky-50 text-sky-700 dark:bg-sky-900/40 dark:text-sky-400",
  violet: "bg-violet-50 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400",
};

const dotStyles: Record<BadgeVariant, string> = {
  neutral: "bg-slate-400",
  indigo: "bg-indigo-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  danger: "bg-red-500",
  info: "bg-sky-500",
  violet: "bg-violet-500",
};

export function Badge({
  variant = "neutral",
  size = "sm",
  dot,
  pulsing,
  children,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-[4px] font-medium",
        size === "sm" ? "h-5 px-2 text-[11px]" : "h-6 px-2.5 text-xs",
        variantStyles[variant],
        className
      )}
    >
      {dot && (
        <span className={cn("size-1.5 rounded-full flex-shrink-0", dotStyles[variant], pulsing && "animate-pulse")} />
      )}
      {children}
    </span>
  );
}

export function RunStatusBadge({ status }: { status: RunStatus | string }) {
  const config: Record<RunStatus, { variant: BadgeVariant; label: string; pulsing?: boolean }> = {
    running: { variant: "indigo", label: "Running", pulsing: true },
    success: { variant: "success", label: "Success" },
    failed: { variant: "danger", label: "Failed" },
    pending: { variant: "warning", label: "Pending" },
    cancelled: { variant: "neutral", label: "Cancelled" },
  };
  const known = config[status as RunStatus];
  const variant = known?.variant ?? "neutral";
  const pulsing = known?.pulsing ?? false;
  const label =
    known?.label ??
    status
      .toString()
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <Badge variant={variant} size="sm" dot pulsing={pulsing}>
      {label}
    </Badge>
  );
}

