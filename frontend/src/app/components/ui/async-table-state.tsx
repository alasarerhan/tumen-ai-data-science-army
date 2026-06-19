import React from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { Button } from "./button";

interface AsyncTableStateProps {
  isLoading: boolean;
  error?: string | null;
  isEmpty?: boolean;
  colSpan: number;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function AsyncTableState({
  isLoading,
  error,
  isEmpty,
  colSpan,
  emptyTitle = "No records found.",
  emptyDescription = "Adjust your filters and try again.",
  onRetry,
  children,
}: AsyncTableStateProps) {
  if (isLoading) {
    return (
      <tr>
        <td colSpan={colSpan} className="py-12">
          <div className="sr-only" role="status" aria-live="polite" aria-busy="true">Loading table rows</div>
          <div className="flex items-center justify-center gap-2 text-sm text-slate-500">
            <Loader2 size={16} className="animate-spin" />
            Loading…
          </div>
        </td>
      </tr>
    );
  }

  if (error) {
    return (
      <tr>
        <td colSpan={colSpan} className="py-10">
          <div className="flex flex-col items-center justify-center gap-3 text-sm text-red-600" role="alert">
            <div className="flex items-center gap-2">
              <AlertTriangle size={15} />
              <span>{error}</span>
            </div>
            {onRetry ? (
              <Button variant="secondary" size="sm" onClick={onRetry}>
                Retry
              </Button>
            ) : null}
          </div>
        </td>
      </tr>
    );
  }

  if (isEmpty) {
    return (
      <tr>
        <td colSpan={colSpan} className="py-16 text-center">
          <div className="flex flex-col items-center gap-2" role="status" aria-live="polite">
            <Inbox size={28} className="text-slate-300" />
            <p className="text-sm font-medium text-slate-600">{emptyTitle}</p>
            <p className="text-xs text-slate-400">{emptyDescription}</p>
          </div>
        </td>
      </tr>
    );
  }

  return <>{children}</>;
}
