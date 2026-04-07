import React, { useState } from "react";
import { RefreshCw, Play, AlertCircle, CheckCircle2 } from "lucide-react";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { AsyncState } from "../ui/async-state";
import type { DlqEvent } from "../../api/admin";
import { cn } from "../../lib/utils";

interface DlqTableProps {
  events: DlqEvent[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onReplay: (eventId: string) => Promise<void>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
}

export function DlqTable({ events, loading, error, onRefresh, onReplay }: DlqTableProps) {
  const [replayingId, setReplayingId] = useState<string | null>(null);

  const handleReplay = async (eventId: string) => {
    setReplayingId(eventId);
    try {
      await onReplay(eventId);
      onRefresh();
    } finally {
      setReplayingId(null);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-700">Dead Letter Queue</h3>
          {events.length > 0 && (
            <Badge variant="warning" size="sm">
              {events.length} failed
            </Badge>
          )}
        </div>
        <Button
          variant="ghost"
          size="xs"
          leadingIcon={<RefreshCw size={12} />}
          onClick={onRefresh}
          loading={loading}
        >
          Refresh
        </Button>
      </div>

      <AsyncState
        isLoading={loading}
        error={error}
        isEmpty={!loading && events.length === 0}
        emptyTitle="No failed events"
        emptyDescription="All events processed successfully."
        className="p-8"
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left">
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase">Event Type</th>
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase">Aggregate</th>
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase">Error</th>
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase">Retries</th>
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase">Failed</th>
                <th className="px-4 py-2 text-xs font-medium text-slate-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {events.map((event) => (
                <tr key={event.id} className="hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <code className="rounded bg-slate-100 px-1 text-xs">{event.event_type}</code>
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-600">
                    {event.aggregate_type}/{event.aggregate_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-1 text-xs text-red-600 max-w-[200px] truncate">
                      <AlertCircle size={12} className="flex-shrink-0" />
                      <span className="truncate" title={event.final_error || "Unknown error"}>
                        {event.final_error || "Unknown error"}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-2 text-xs text-slate-500">{event.retry_count}</td>
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {formatTimeAgo(event.moved_to_dlq_at)}
                  </td>
                  <td className="px-4 py-2">
                    <Button
                      variant="secondary"
                      size="xs"
                      leadingIcon={<Play size={10} />}
                      onClick={() => handleReplay(event.id)}
                      loading={replayingId === event.id}
                    >
                      Replay
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </AsyncState>
    </div>
  );
}
