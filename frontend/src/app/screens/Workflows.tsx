import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router";
import { Archive, Copy, GitBranch, MoreHorizontal, Pencil, Plus, Search, CalendarClock, Pause, Play } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import { useWorkflows, useArchiveWorkflow } from "../hooks/useWorkflows";
import { useSchedules, usePauseSchedule, useResumeSchedule } from "../hooks/useSchedules";
import { type WorkflowSpec } from "../api/workflows";
import { type ScheduledDeployment } from "../api/scheduler";
import { ScheduleStatusBadge, formatNextRun } from "../components/workflow/ScheduleBadge";
import { formatRelativeTime } from "../utils/time";
import { cn } from "../lib/utils";

type WorkflowStatus = WorkflowSpec["status"];
type WorkflowValidationStatus = WorkflowSpec["validation_summary"]["status"];

const statusVariant: Record<WorkflowStatus, "success" | "warning" | "neutral"> = {
  published: "success",
  draft: "warning",
  archived: "neutral",
};

const validationVariant: Record<WorkflowValidationStatus, "success" | "warning" | "danger"> = {
  safe: "success",
  advisory: "warning",
  invalid: "danger",
};

const validationLabel: Record<WorkflowValidationStatus, string> = {
  safe: "Chain Safe",
  advisory: "Advisory",
  invalid: "Invalid Chain",
};

export default function Workflows() {
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [search, setSearch] = useState("");
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const { data: workflowsData, isLoading: loadingWfs, error: wfsError, refetch: fetchWorkflows } = useWorkflows(workspaceId);
  const { data: schedulesData } = useSchedules(workspaceId);
  const archiveMutation = useArchiveWorkflow();
  const pauseMutation = usePauseSchedule();
  const resumeMutation = useResumeSchedule();

  const workflows = workflowsData?.items ?? [];
  const schedules = useMemo(() => {
    const map = new Map<string, ScheduledDeployment>();
    if (schedulesData?.items) {
      for (const schedule of schedulesData.items) {
        map.set(schedule.workflow_spec_id, schedule);
      }
    }
    return map;
  }, [schedulesData]);

  const handleArchive = async (id: string) => {
    if (!workspaceId) return;
    await archiveMutation.mutateAsync({ id, workspace_id: workspaceId }).catch((err: unknown) => {
      console.error("Failed to archive workflow:", err);
    });
  };

  const handleToggleSchedule = async (wf: WorkflowSpec) => {
    if (!workspaceId) return;
    const schedule = schedules.get(wf.id);
    if (!schedule) return;

    try {
      if (schedule.enabled) {
        await pauseMutation.mutateAsync({ deployment_id: schedule.deployment_id, workspace_id: workspaceId });
      } else {
        await resumeMutation.mutateAsync({ deployment_id: schedule.deployment_id, workspace_id: workspaceId });
      }
    } catch (err) {
      console.error("Failed to toggle schedule:", err);
    }
  };

  const filtered = workflows.filter((wf) => wf.name.toLowerCase().includes(search.toLowerCase()));

  return (
    <AppShell>
      <div className="mx-auto max-w-[1280px] space-y-5 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
              Workflows
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Build, publish, and manage your agent pipelines.
            </p>
          </div>
          <Button variant="primary" size="md" leadingIcon={<Plus size={14} />} onClick={() => navigate("/workflows/new/designer")}>
            New Workflow
          </Button>
        </div>

        <div className="relative max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search workflows..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="h-9 w-full rounded-[6px] border border-slate-200 bg-white pl-8 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
          />
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          <AsyncState
            isLoading={loadingWfs}
            error={wfsError?.message ?? null}
            isEmpty={!loadingWfs && !wfsError && filtered.length === 0}
            emptyTitle="No workflows yet"
            emptyDescription="Create your first workflow to start building pipelines."
            onRetry={() => fetchWorkflows()}
            className="col-span-3 py-12"
          >
            {filtered.map((wf) => {
              const schedule = schedules.get(wf.id);
              const spec = wf.spec as Record<string, unknown>;
              const scheduleInfo = spec?.schedule as Record<string, unknown> | undefined;
              const cron = (scheduleInfo?.cron as string) || schedule?.cron;
              const validation = wf.validation_summary;

              return (
                <div
                  key={wf.id}
                  className="group cursor-pointer rounded-[8px] border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900"
                  onClick={() => navigate(`/workflows/${wf.id}`)}
                >
                  <div className="p-5">
                    <div className="mb-3 flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <div className="flex size-8 items-center justify-center rounded-[6px] bg-indigo-50 dark:bg-indigo-900/30">
                          <GitBranch size={16} className="text-indigo-600 dark:text-indigo-400" />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{wf.name}</p>
                          <p className="font-mono text-xs text-slate-400">v{wf.version}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={statusVariant[wf.status]} size="sm">
                          {wf.status.charAt(0).toUpperCase() + wf.status.slice(1)}
                        </Badge>
                        <Badge variant={validationVariant[validation.status]} size="sm">
                          {validationLabel[validation.status]}
                        </Badge>
                        {schedule && (
                          <ScheduleStatusBadge hasSchedule={!!schedule} enabled={schedule.enabled} />
                        )}
                        <div className="relative" onClick={(event) => event.stopPropagation()}>
                          <button
                            onClick={() => setOpenMenu(openMenu === wf.id ? null : wf.id)}
                            className="rounded p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                            aria-label="Workflow actions"
                          >
                            <MoreHorizontal size={15} />
                          </button>
                          {openMenu === wf.id ? (
                            <div className="absolute right-0 top-full z-20 mt-1 w-44 rounded-[8px] border border-slate-200 bg-white py-1 shadow-md dark:border-slate-700 dark:bg-slate-800">
                              {[
                                { label: "Open in Designer", icon: <Pencil size={13} />, action: () => navigate(`/workflows/${wf.id}/designer`) },
                                { label: "Duplicate", icon: <Copy size={13} /> },
                                ...(schedule
                                  ? [{
                                      label: schedule.enabled ? "Pause Schedule" : "Resume Schedule",
                                      icon: schedule.enabled ? <Pause size={13} /> : <Play size={13} />,
                                      action: () => handleToggleSchedule(wf),
                                    }]
                                  : []),
                                { label: "Archive", icon: <Archive size={13} />, action: () => handleArchive(wf.id) },
                              ].map((item) => (
                                <button
                                  key={item.label}
                                  onClick={() => {
                                    setOpenMenu(null);
                                    item.action?.();
                                  }}
                                  className={cn(
                                    "w-full px-3 py-2 text-sm transition-colors",
                                    "flex items-center gap-2 text-slate-700 hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700"
                                  )}
                                >
                                  {item.icon}
                                  {item.label}
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    <p className="mb-4 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
                      {((wf.spec as Record<string, unknown>)?.description as string) ?? "No description."}
                    </p>
                    {validation.status !== "safe" ? (
                      <p className={cn(
                        "mb-4 rounded px-2 py-1 text-[11px]",
                        validation.status === "invalid"
                          ? "bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-300"
                          : "bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300",
                      )}>
                        {validation.status === "invalid"
                          ? `${validation.error_count} chain error`
                          : `${validation.warning_count} advisory warning`}
                      </p>
                    ) : null}

                    <div className="flex items-center justify-between">
                      <span className="text-xs text-slate-500">{formatRelativeTime(wf.updated_at)}</span>
                      {schedule && schedule.enabled && schedule.next_run_at && (
                        <span className="flex items-center gap-1 text-xs text-emerald-600">
                          <CalendarClock size={10} />
                          {formatNextRun(schedule.next_run_at)}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-2 border-t border-slate-100 px-5 py-2.5 dark:border-slate-800">
                    <Button
                      variant="secondary"
                      size="xs"
                      onClick={(event) => {
                        event.stopPropagation();
                        navigate(`/workflows/${wf.id}/designer`);
                      }}
                    >
                      Open Designer
                    </Button>
                    <Button variant="ghost" size="xs">
                      View Spec
                    </Button>
                  </div>
                </div>
              );
            })}
          </AsyncState>
        </div>
      </div>
    </AppShell>
  );
}
