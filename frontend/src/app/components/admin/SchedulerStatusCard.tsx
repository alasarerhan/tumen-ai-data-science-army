import React from "react";
import { Crown, Clock, CheckCircle2, XCircle, Pause, Play } from "lucide-react";
import { Badge } from "../ui/badge";
import { cn } from "../../lib/utils";
import type { SchedulerStatus } from "../../api/admin";

interface SchedulerStatusCardProps {
  status: SchedulerStatus | null;
  loading: boolean;
  className?: string;
}

export function SchedulerStatusCard({ status, loading, className }: SchedulerStatusCardProps) {
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

  if (!status) {
    return (
      <div className={cn("rounded-lg border border-slate-200 bg-white p-4", className)}>
        <p className="text-sm text-slate-500">Scheduler status unavailable</p>
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border border-slate-200 bg-white p-4", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-700">Scheduler</h3>
        <Badge variant={status.is_leader ? "success" : "neutral"} size="sm">
          {status.is_leader ? "Leader" : "Follower"}
        </Badge>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs">
          {status.is_leader ? (
            <Crown size={14} className="text-amber-500" />
          ) : (
            <Clock size={14} className="text-slate-400" />
          )}
          <span className="text-slate-600">
            {status.is_leader
              ? `Leading: ${status.leader_id?.slice(0, 12)}...`
              : "Waiting for leadership"}
          </span>
        </div>

        <div className="border-t border-slate-100 pt-3">
          <p className="text-xs font-medium text-slate-500 mb-2">Scheduled Jobs</p>
          <div className="space-y-2">
            {status.jobs.map((job) => (
              <div
                key={job.job_name}
                className="flex items-center justify-between text-xs"
              >
                <div className="flex items-center gap-2">
                  {job.enabled ? (
                    <Play size={12} className="text-emerald-500" />
                  ) : (
                    <Pause size={12} className="text-slate-400" />
                  )}
                  <span className="text-slate-700">{job.job_name}</span>
                </div>
                <div className="flex items-center gap-2">
                  {job.last_run_status && (
                    <span
                      className={cn(
                        "inline-flex items-center gap-1",
                        job.last_run_status === "success"
                          ? "text-emerald-600"
                          : "text-red-600",
                      )}
                    >
                      {job.last_run_status === "success" ? (
                        <CheckCircle2 size={12} />
                      ) : (
                        <XCircle size={12} />
                      )}
                    </span>
                  )}
                  <span className="text-slate-400">{job.job_type}</span>
                </div>
              </div>
            ))}
            {status.jobs.length === 0 && (
              <p className="text-xs text-slate-400">No scheduled jobs</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
