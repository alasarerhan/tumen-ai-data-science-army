import React, { useState, useMemo } from "react";
import { useNavigate } from "react-router";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  MoreHorizontal,
  Play,
  RefreshCw,
  Search,
  Trash2,
  X,
  XCircle,
} from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Badge, RunStatusBadge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AsyncTableState } from "../components/ui/async-table-state";
import { useAuth } from "../context/AuthContext";
import { useRuns, useTriggerRun, useRetryRun, useCancelRun } from "../hooks/useRuns";
import { useWorkflows } from "../hooks/useWorkflows";
import { type Run, type RunStatus } from "../api/runs";
import { formatDuration, formatRelativeTime } from "../utils/time";
import { cn } from "../lib/utils";
import {
  getWorkflowValidationLabel,
  getWorkflowValidationVariant,
  resolveWorkflowValidationForFlowKey,
} from "../utils/workflowValidation";

const STATUS_OPTIONS: { value: RunStatus | "all"; label: string }[] = [
  { value: "all", label: "All Statuses" },
  { value: "running", label: "Running" },
  { value: "success", label: "Success" },
  { value: "failed", label: "Failed" },
  { value: "pending", label: "Pending" },
  { value: "cancelled", label: "Cancelled" },
];

export default function RunsList() {
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<RunStatus | "all">("all");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  const { data: runsData, isLoading: loadingRuns, error: runsError, refetch: fetchRuns } = useRuns(workspaceId);
  const { data: workflowsData } = useWorkflows(workspaceId);
  const triggerMutation = useTriggerRun();
  const retryMutation = useRetryRun(workspaceId);
  const cancelMutation = useCancelRun(workspaceId);

  const runs = runsData?.items ?? [];
  const workflows = workflowsData?.items ?? [];

  const handleTriggerRun = async () => {
    if (!workspaceId) return;
    await triggerMutation.mutateAsync({ workspace_id: workspaceId });
  };

  const filtered = runs.filter((run) => {
    const matchSearch =
      run.flow_key.toLowerCase().includes(search.toLowerCase()) ||
      run.id.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || run.status === statusFilter;
    return matchSearch && matchStatus;
  });

  const allSelected = filtered.length > 0 && filtered.every((run) => selected.has(run.id));

  const toggleAll = () => {
    if (allSelected) {
      setSelected(new Set());
      return;
    }
    setSelected(new Set(filtered.map((run) => run.id)));
  };

  const toggleRow = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const clearFilters = () => {
    setSearch("");
    setStatusFilter("all");
  };

  const hasFilters = search.trim().length > 0 || statusFilter !== "all";

  const handleRetry = async (runId: string) => {
    if (!workspaceId) return;
    setOpenMenu(null);
    await retryMutation.mutateAsync(runId);
  };

  const handleCancel = async (runId: string) => {
    if (!workspaceId) return;
    setOpenMenu(null);
    await cancelMutation.mutateAsync(runId);
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-[1280px] space-y-5 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
              Pipeline Runs
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              All workflow executions across your workspace.
            </p>
          </div>
          <Button variant="primary" size="md" leadingIcon={<Play size={14} />} loading={triggerMutation.isPending} onClick={handleTriggerRun}>
            Trigger Run
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-[8px] border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="relative min-w-[200px] flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search runs..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-8 w-full rounded-[6px] border border-slate-200 bg-slate-50 pl-8 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div className="relative">
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as RunStatus | "all")}
              className="h-8 cursor-pointer appearance-none rounded-[6px] border border-slate-200 bg-white pl-3 pr-8 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <ChevronDown size={12} className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          </div>

          {hasFilters ? (
            <Button variant="ghost" size="sm" leadingIcon={<X size={13} />} onClick={clearFilters}>
              Clear Filters
            </Button>
          ) : null}

          <span className="ml-auto whitespace-nowrap text-xs text-slate-400">
            Showing {filtered.length} of {runs.length} runs
          </span>
        </div>

        {selected.size > 0 ? (
          <div className="flex items-center gap-3 rounded-[8px] border border-indigo-200 bg-indigo-50 px-4 py-2.5 dark:border-indigo-700 dark:bg-indigo-900/20">
            <span className="text-sm font-medium text-indigo-700 dark:text-indigo-300">{selected.size} selected</span>
            <div className="ml-auto flex gap-2">
              <Button variant="secondary" size="sm" leadingIcon={<RefreshCw size={13} />}>
                Retry
              </Button>
              <Button variant="secondary" size="sm" leadingIcon={<XCircle size={13} />}>
                Cancel
              </Button>
              <Button variant="destructive" size="sm" leadingIcon={<Trash2 size={13} />}>
                Delete
              </Button>
            </div>
          </div>
        ) : null}

        <div className="overflow-hidden rounded-[8px] border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-800">
                  <th className="w-10 px-4 py-3">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={toggleAll}
                      className="rounded border-slate-300 text-indigo-600"
                      aria-label="Select all"
                    />
                  </th>
                  {["Status", "Run ID", "Workflow", "Triggered By", "Started", "Duration", "Artifacts", "Actions"].map((header) => (
                    <th
                      key={header}
                      className="whitespace-nowrap px-3 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                <AsyncTableState
                  isLoading={loadingRuns}
                  error={runsError?.message ?? null}
                  isEmpty={!loadingRuns && !runsError && filtered.length === 0}
                  colSpan={9}
                  emptyTitle="No runs found."
                  emptyDescription="Adjust filters or trigger a new run."
                  onRetry={() => fetchRuns()}
                >
                  {filtered.map((run) => {
                    const workflowValidation = resolveWorkflowValidationForFlowKey(workflows, run.flow_key);
                    return (
                    <tr
                      key={run.id}
                      className={cn(
                        "group cursor-pointer transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50",
                        selected.has(run.id) && "bg-indigo-50/50 dark:bg-indigo-900/10",
                        run.status === "running" && "border-l-2 border-l-indigo-500"
                      )}
                      onClick={() => navigate(`/runs/${run.id}`)}
                    >
                      <td className="px-4 py-3" onClick={(event) => event.stopPropagation()}>
                        <input
                          type="checkbox"
                          checked={selected.has(run.id)}
                          onChange={() => toggleRow(run.id)}
                          className="rounded border-slate-300 text-indigo-600"
                          aria-label={`Select run ${run.id}`}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <RunStatusBadge status={run.status} />
                      </td>
                      <td className="px-3 py-3">
                        <div className="group/id flex items-center gap-1.5">
                          <code className="max-w-[120px] truncate font-mono text-xs text-slate-600 dark:text-slate-300">{run.id}</code>
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              void navigator.clipboard.writeText(run.id);
                            }}
                            className="text-slate-400 opacity-0 transition-opacity hover:text-slate-600 group-hover/id:opacity-100"
                            aria-label="Copy run ID"
                          >
                            <Copy size={12} />
                          </button>
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <div className="space-y-1">
                          <p className="max-w-[180px] truncate font-medium text-slate-800 dark:text-slate-200">{run.flow_key || "--"}</p>
                          {workflowValidation ? (
                            <Badge variant={getWorkflowValidationVariant(workflowValidation.status)} size="sm">
                              {getWorkflowValidationLabel(workflowValidation.status)}
                            </Badge>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span className="text-xs text-slate-400">--</span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-3 text-xs text-slate-500 dark:text-slate-400" title={run.started_at ?? ""}>
                        {formatRelativeTime(run.started_at)}
                      </td>
                      <td className="px-3 py-3 font-mono text-xs tabular-nums text-slate-600 dark:text-slate-300">
                        {formatDuration(run.started_at, run.finished_at)}
                      </td>
                      <td className="px-3 py-3">
                        <span className="text-xs text-slate-400">--</span>
                      </td>
                      <td className="px-3 py-3" onClick={(event) => event.stopPropagation()}>
                        <div className="relative">
                          <button
                            onClick={() => setOpenMenu(openMenu === run.id ? null : run.id)}
                            className="rounded-[6px] p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800"
                            aria-label="Run actions"
                          >
                            <MoreHorizontal size={15} />
                          </button>
                          {openMenu === run.id ? (
                            <div className="absolute right-0 top-full z-20 mt-1 w-40 rounded-[8px] border border-slate-200 bg-white py-1 shadow-md dark:border-slate-700 dark:bg-slate-800">
                              {[
                                { label: "View Detail", icon: <Search size={13} />, action: () => navigate(`/runs/${run.id}`) },
                                { label: "Re-run", icon: <RefreshCw size={13} />, action: () => handleRetry(run.id) },
                                { label: "Cancel", icon: <XCircle size={13} />, action: () => handleCancel(run.id) },
                              ].map((action) => (
                                <button
                                  key={action.label}
                                  onClick={() => {
                                    action.action();
                                    setOpenMenu(null);
                                  }}
                                  className="flex w-full items-center gap-2 px-3 py-2 text-sm text-slate-700 transition-colors hover:bg-slate-50 dark:text-slate-200 dark:hover:bg-slate-700"
                                >
                                  {action.icon}
                                  {action.label}
                                </button>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                    );
                  })}
                </AsyncTableState>
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 dark:border-slate-800">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Rows per page:</span>
              <select className="h-7 rounded border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                <option>10</option>
                <option>25</option>
                <option>50</option>
              </select>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-500">1-{filtered.length} of {filtered.length}</span>
              <div className="flex gap-1">
                <button className="rounded p-1 text-slate-400 hover:bg-slate-100 disabled:opacity-30" disabled aria-label="Previous page">
                  <ChevronLeft size={15} />
                </button>
                <button className="rounded bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white">1</button>
                <button className="rounded p-1 text-slate-400 hover:bg-slate-100 disabled:opacity-30" disabled aria-label="Next page">
                  <ChevronRight size={15} />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
