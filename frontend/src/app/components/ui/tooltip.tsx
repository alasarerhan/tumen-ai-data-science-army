import React from "react";
import { cn } from "../../lib/utils";

interface TooltipProps {
  children: React.ReactNode;
}

interface TooltipTriggerProps {
  children: React.ReactElement;
  asChild?: boolean;
}

interface TooltipContentProps {
  children: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  className?: string;
}

export function Tooltip({ children }: TooltipProps) {
  return <span className="group/tooltip relative inline-flex">{children}</span>;
}

export function TooltipTrigger({ children }: TooltipTriggerProps) {
  return React.cloneElement(children, {
    "aria-describedby": "tooltip-content",
  } as Partial<React.HTMLAttributes<HTMLElement>>);
}

export function TooltipContent({ children, side = "top", className }: TooltipContentProps) {
  const sideClass =
    side === "right"
      ? "left-full top-1/2 ml-2 -translate-y-1/2"
      : side === "left"
        ? "right-full top-1/2 mr-2 -translate-y-1/2"
        : side === "bottom"
          ? "left-1/2 top-full mt-2 -translate-x-1/2"
          : "bottom-full left-1/2 mb-2 -translate-x-1/2";

  return (
    <span
      id="tooltip-content"
      role="tooltip"
      className={cn(
        "pointer-events-none absolute z-50 whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover/tooltip:opacity-100 group-focus-within/tooltip:opacity-100",
        sideClass,
        className,
      )}
    >
      {children}
    </span>
  );
}
