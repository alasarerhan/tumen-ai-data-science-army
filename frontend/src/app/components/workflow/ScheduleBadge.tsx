import { CalendarClock, Pause, Play, Clock } from "lucide-react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { cn } from "../../lib/utils";

interface ScheduleBadgeProps {
  cron: string;
  enabled: boolean;
  nextRunAt: string | null;
  onToggle?: () => void;
  compact?: boolean;
}

export function formatNextRun(nextRunAt: string | null): string {
  if (!nextRunAt) return "Not scheduled";
  const date = new Date(nextRunAt);
  if (Number.isNaN(date.getTime())) return "Invalid date";
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  if (diffMs < 0) return "Overdue";
  if (diffMs < 60_000) return "In less than a minute";
  if (diffMs < 3_600_000) {
    const mins = Math.floor(diffMs / 60_000);
    return `In ${mins} minute${mins > 1 ? "s" : ""}`;
  }
  if (diffMs < 86_400_000) {
    const hours = Math.floor(diffMs / 3_600_000);
    return `In ${hours} hour${hours > 1 ? "s" : ""}`;
  }
  const days = Math.floor(diffMs / 86_400_000);
  return `In ${days} day${days > 1 ? "s" : ""}`;
}

export function ScheduleBadge({
  cron,
  enabled,
  nextRunAt,
  onToggle,
  compact = false,
}: ScheduleBadgeProps) {
  if (compact) {
    return (
      <div className="inline-flex items-center gap-1">
        <CalendarClock size={12} className={enabled ? "text-emerald-500" : "text-slate-400"} />
        <span className="text-xs text-slate-500">
          {enabled ? formatNextRun(nextRunAt) : "Paused"}
        </span>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarClock size={14} className={enabled ? "text-emerald-500" : "text-slate-400"} />
          <span className="text-sm font-medium text-slate-700">Schedule</span>
        </div>
        <Badge variant={enabled ? "success" : "neutral"} size="sm">
          {enabled ? "Active" : "Paused"}
        </Badge>
      </div>
      <div className="mt-2 space-y-1">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Clock size={12} />
          <code className="rounded bg-slate-100 px-1 font-mono">{cron}</code>
        </div>
        {enabled && nextRunAt && (
          <p className="text-xs text-slate-500">Next run: {formatNextRun(nextRunAt)}</p>
        )}
      </div>
      {onToggle && (
        <Button
          variant="secondary"
          size="xs"
          fullWidth
          className="mt-2"
          leadingIcon={enabled ? <Pause size={12} /> : <Play size={12} />}
          onClick={onToggle}
        >
          {enabled ? "Pause Schedule" : "Resume Schedule"}
        </Button>
      )}
    </div>
  );
}

interface ScheduleStatusBadgeProps {
  hasSchedule: boolean;
  enabled: boolean;
  className?: string;
}

export function ScheduleStatusBadge({ hasSchedule, enabled, className }: ScheduleStatusBadgeProps) {
  if (!hasSchedule) {
    return (
      <Badge variant="neutral" size="sm" className={cn("gap-1", className)}>
        <CalendarClock size={10} />
        Not scheduled
      </Badge>
    );
  }
  return (
    <Badge variant={enabled ? "success" : "warning"} size="sm" className={cn("gap-1", className)}>
      <CalendarClock size={10} />
      {enabled ? "Scheduled" : "Paused"}
    </Badge>
  );
}
