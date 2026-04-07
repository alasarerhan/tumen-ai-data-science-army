import React from "react";
import { Cpu, TrendingUp, TrendingDown, AlertTriangle, CheckCircle2 } from "lucide-react";
import { cn } from "../../lib/utils";
import type { MemoryStats } from "../../api/admin";

interface MemoryMetricsCardProps {
  stats: MemoryStats | null;
  loading: boolean;
  className?: string;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

export function MemoryMetricsCard({ stats, loading, className }: MemoryMetricsCardProps) {
  if (loading) {
    return (
      <div className={cn("rounded-lg border border-slate-200 bg-white p-4", className)}>
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-slate-200 rounded w-1/3" />
          <div className="h-8 bg-slate-200 rounded w-1/2" />
        </div>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className={cn("rounded-lg border border-slate-200 bg-white p-4", className)}>
        <p className="text-sm text-slate-500">Memory stats unavailable</p>
      </div>
    );
  }

  const memoryHealth = stats.percent > 80 ? "critical" : stats.percent > 60 ? "warning" : "healthy";
  const growthRateMB = stats.growth_rate_bytes_per_minute / (1024 * 1024);
  const isLeaking = growthRateMB > 10;

  return (
    <div className={cn("rounded-lg border border-slate-200 bg-white p-4", className)}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">Memory</h3>
        <span
          className={cn(
            "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
            memoryHealth === "healthy" && "bg-emerald-50 text-emerald-700",
            memoryHealth === "warning" && "bg-amber-50 text-amber-700",
            memoryHealth === "critical" && "bg-red-50 text-red-700",
          )}
        >
          {memoryHealth === "healthy" && <CheckCircle2 size={12} />}
          {memoryHealth === "warning" && <AlertTriangle size={12} />}
          {memoryHealth === "critical" && <AlertTriangle size={12} />}
          {stats.percent.toFixed(1)}%
        </span>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Cpu size={14} className="text-slate-400" />
          <div className="flex-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-500">RSS</span>
              <span className="font-medium text-slate-700">{formatBytes(stats.rss_bytes)}</span>
            </div>
            <div className="mt-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  memoryHealth === "healthy" && "bg-emerald-500",
                  memoryHealth === "warning" && "bg-amber-500",
                  memoryHealth === "critical" && "bg-red-500",
                )}
                style={{ width: `${Math.min(stats.percent, 100)}%` }}
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs">
          <span className="text-slate-500">Growth rate</span>
          <span
            className={cn(
              "inline-flex items-center gap-1",
              isLeaking ? "text-red-600" : "text-slate-600",
            )}
          >
            {isLeaking ? (
              <TrendingUp size={12} className="text-red-500" />
            ) : (
              <TrendingDown size={12} className="text-emerald-500" />
            )}
            {growthRateMB.toFixed(1)} MB/min
          </span>
        </div>

        {stats.recommendations.length > 0 && (
          <div className="border-t border-slate-100 pt-3">
            <p className="text-xs text-slate-500">{stats.recommendations[0]}</p>
          </div>
        )}
      </div>
    </div>
  );
}
