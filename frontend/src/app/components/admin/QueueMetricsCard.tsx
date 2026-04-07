import React from "react";
import { Inbox, Clock, AlertCircle, CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";

interface QueueMetricsCardProps {
  pending: number;
  processing: number;
  failed: number;
  dlq: number;
  className?: string;
}

export function QueueMetricsCard({ pending, processing, failed, dlq, className }: QueueMetricsCardProps) {
  const total = pending + processing + failed + dlq;
  const healthStatus = dlq > 10 ? "critical" : dlq > 0 ? "warning" : "healthy";

  return (
    <div className={cn("rounded-lg border border-slate-200 bg-white p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">Outbox Queue</h3>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
            healthStatus === "healthy" && "bg-emerald-50 text-emerald-700",
            healthStatus === "warning" && "bg-amber-50 text-amber-700",
            healthStatus === "critical" && "bg-red-50 text-red-700",
          )}
        >
          {healthStatus === "healthy" && <CheckCircle2 size={12} />}
          {healthStatus === "warning" && <AlertCircle size={12} />}
          {healthStatus === "critical" && <AlertCircle size={12} />}
          {healthStatus === "healthy" ? "Healthy" : healthStatus === "warning" ? "Warning" : "Critical"}
        </span>
      </div>

      <div className="grid grid-cols-4 gap-2">
        <MetricItem
          icon={<Clock size={14} className="text-blue-500" />}
          label="Pending"
          value={pending}
          color="text-blue-600"
        />
        <MetricItem
          icon={<Inbox size={14} className="text-indigo-500" />}
          label="Processing"
          value={processing}
          color="text-indigo-600"
        />
        <MetricItem
          icon={<AlertCircle size={14} className="text-red-500" />}
          label="Failed"
          value={failed}
          color="text-red-600"
        />
        <MetricItem
          icon={<Inbox size={14} className="text-amber-500" />}
          label="DLQ"
          value={dlq}
          color="text-amber-600"
          highlight={dlq > 0}
        />
      </div>

      <div className="mt-3 pt-3 border-t border-slate-100">
        <div className="flex items-center justify-between text-xs text-slate-500">
          <span>Total events</span>
          <span className="font-medium text-slate-700">{total}</span>
        </div>
      </div>
    </div>
  );
}

function MetricItem({
  icon,
  label,
  value,
  color,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "text-center p-2 rounded",
        highlight && "bg-amber-50 ring-1 ring-amber-200",
      )}
    >
      <div className="flex justify-center mb-1">{icon}</div>
      <div className={cn("text-lg font-bold", color)}>{value}</div>
      <div className="text-[10px] text-slate-500 uppercase tracking-wide">{label}</div>
    </div>
  );
}
