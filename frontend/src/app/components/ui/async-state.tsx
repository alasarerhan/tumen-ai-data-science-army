import React from "react";
import { AlertTriangle, Loader2, Inbox } from "lucide-react";
import { Button } from "./button";

interface AsyncStateProps {
  isLoading: boolean;
  error?: string | null;
  isEmpty?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  className?: string;
  children: React.ReactNode;
}

export function AsyncState({
  isLoading,
  error,
  isEmpty,
  emptyTitle = "No data yet",
  emptyDescription = "Try adjusting your filters or create a new record.",
  onRetry,
  className,
  children,
}: AsyncStateProps) {
  if (isLoading) {
    return (
      <div className={className ?? "flex h-40 items-center justify-center"} role="status" aria-live="polite" aria-busy="true">
        <div className="flex items-center gap-2 text-slate-500">
          <Loader2 size={18} className="animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={className ?? "flex h-40 items-center justify-center"} role="alert">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle size={18} />
            <span className="text-sm">{error}</span>
          </div>
          {onRetry ? (
            <Button variant="secondary" size="sm" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className={className ?? "flex h-40 items-center justify-center"} role="status" aria-live="polite">
        <div className="flex flex-col items-center gap-2 text-center">
          <Inbox size={20} className="text-slate-300" />
          <p className="text-sm font-medium text-slate-600">{emptyTitle}</p>
          <p className="text-xs text-slate-400">{emptyDescription}</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

