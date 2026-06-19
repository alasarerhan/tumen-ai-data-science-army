import { useState } from "react";
import { useNavigate } from "react-router";
import {
  Activity,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Copy,
  Grid3X3,
  Layers3,
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
import { useRuns, useTriggerRun, useRetryRun, useCancelRun, useRunNodesForRuns } from "../hooks/useRuns";
import { useWorkflows } from "../hooks/useWorkflows";
import { type Run, type RunStatus, type WorkflowNodeExecution } from "../api/runs";
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

const MATRIX_RUN_LIMIT = 6;

function shortRunId(id: string) {
  return id.length > 8 ? id.slice(0, 8) : id;
}

function nodeDurationMs(node: WorkflowNodeExecution) {
  if (!node.started_at || !node.finished_at) return null;
  const started = Date.parse(node.started_at);
  const finished = Date.parse(node.finished_at);
  if (!Number.isFinite(started) || !Number.isFinite(finished)) return null;
  return Math.max(0, finished - started);
}

function statusTone(status: string | undefined) {
  const normalized = (status ?? "").toLowerCase();
  if (["succeeded", "success", "completed"].includes(normalized)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300";
  }
  if (["failed", "error"].includes(normalized)) {
    return "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300";
  }
  if (["running", "retrying"].includes(normalized)) {
    return "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300";
  }
  if (["waiting_approval", "queued", "pending"].includes(normalized)) {
    return "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300";
  }
  if (["skipped", "cancelled"].includes(normalized)) {
    return "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300";
  }
  return "border-slate-200 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-500";
}

function statusLabel(status: string | undefined) {
  const normalized = (status ?? "").toLowerCase();
  if (["succeeded", "success", "completed"].includes(normalized)) return "ok";
  if (["waiting_approval"].includes(normalized)) return "wait";
  return normalized || "--";
}

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

  const matrixRuns = filtered.slice(0, MATRIX_RUN_LIMIT);
  const nodeQueries = useRunNodesForRuns(matrixRuns.map((run) => run.id), workspaceId);
  const nodeRowsByRunId = new Map<string, WorkflowNodeExecution[]>();
  matrixRuns.forEach((run, index) => {
    nodeRowsByRunId.set(run.id, nodeQueries[index]?.data?.items ?? []);
  });
  const matrixNodes = Array.from(nodeRowsByRunId.values()).flat();
  const matrixNodeTypes = Array.from(new Set(matrixNodes.map((node) => node.node_type || node.node_id || "unknown"))).sort();
  const matrixLoading = nodeQueries.some((query) => query.isLoading || query.isFetching);
  const matrixHasError = nodeQueries.some((query) => query.error);
  const matrixSummary = matrixNodes.reduce(
    (summary, node) => {
      const status = node.status.toLowerCase();
      const duration = nodeDurationMs(node);
      summary.nodes += 1;
      summary.retries += Number.isFinite(node.retry_count) ? node.retry_count : 0;
      summary.artifacts += node.produced_artifact_ids.length;
      if (["failed", "error", "cancelled"].includes(status)) summary.failures += 1;
      if (duration !== null) {
        summary.durationMs += duration;
        summary.durationCount += 1;
      }
      return summary;
    },
    { nodes: 0, failures: 0, retries: 0, artifacts: 0, durationMs: 0, durationCount: 0 }
  );
  const failureRate = matrixSummary.nodes > 0 ? Math.round((matrixSummary.failures / matrixSummary.nodes) * 100) : 0;
  const avgDurationMs = matrixSummary.durationCount > 0 ? Math.round(matrixSummary.durationMs / matrixSummary.durationCount) : null;

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
              aria-label="Search runs"
              placeholder="Search runs…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="h-8 w-full rounded-[6px] border border-slate-200 bg-slate-50 pl-8 pr-3 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            />
          </div>

          <div className="relative">
            <select
              aria-label="Filter runs by status"
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

        <div className="rounded-[8px] border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                <Grid3X3 size={15} className="text-indigo-500" />
                Workflow Run Matrix
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {matrixRuns.length} recent runs compared by node status, duration, retries, and artifacts.
              </p>
            </div>
            <Badge variant={matrixSummary.failures > 0 ? "warning" : "success"} size="sm">
              {matrixSummary.nodes} node records
            </Badge>
          </div>

          <div className="grid grid-cols-2 border-b border-slate-100 text-xs dark:border-slate-800 sm:grid-cols-4">
            <div className="px-4 py-3">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><Activity size={13} /> Failure rate</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{failureRate}%</p>
            </div>
            <div className="border-l border-slate-100 px-4 py-3 dark:border-slate-800">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><RefreshCw size={13} /> Retries</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{matrixSummary.retries}</p>
            </div>
            <div className="border-l border-slate-100 px-4 py-3 dark:border-slate-800">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><Clock3 size={13} /> Avg node time</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {avgDurationMs === null ? "--" : formatDuration(new Date(0).toISOString(), new Date(avgDurationMs).toISOString())}
              </p>
            </div>
            <div className="border-l border-slate-100 px-4 py-3 dark:border-slate-800">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><Layers3 size={13} /> Artifacts</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{matrixSummary.artifacts}</p>
            </div>
          </div>

          {matrixLoading ? (
            <div className="px-4 py-5 text-sm text-slate-500 dark:text-slate-400" role="status" aria-live="polite" aria-busy="true">Loading node matrix…</div>
          ) : matrixHasError ? (
            <div className="px-4 py-5 text-sm text-rose-600 dark:text-rose-300">Node matrix could not be loaded.</div>
          ) : matrixNodeTypes.length === 0 ? (
            <div className="px-4 py-5 text-sm text-slate-500 dark:text-slate-400">No node execution records for the current run set.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] table-fixed text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left dark:border-slate-800">
                    <th className="w-44 px-4 py-2 font-medium uppercase text-slate-400">Node</th>
                    {matrixRuns.map((run: Run) => (
                      <th key={run.id} className="px-2 py-2 font-medium uppercase text-slate-400">
                        <button
                          type="button"
                          className="max-w-full truncate rounded text-left hover:text-indigo-600"
                          onClick={() => navigate(`/runs/${run.id}`)}
                          title={run.id}
                        >
                          {shortRunId(run.id)}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrixNodeTypes.map((nodeType) => (
                    <tr key={nodeType} className="border-b border-slate-100 last:border-b-0 dark:border-slate-800">
                      <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-200">
                        <span className="block truncate" title={nodeType}>{nodeType}</span>
                      </td>
                      {matrixRuns.map((run) => {
                        const node = nodeRowsByRunId.get(run.id)?.find((item) => (item.node_type || item.node_id || "unknown") === nodeType);
                        const artifactCount = node?.produced_artifact_ids.length ?? 0;
                        return (
                          <td key={`${run.id}-${nodeType}`} className="px-2 py-2 align-top">
                            {node ? (
                              <button
                                type="button"
                                className={cn("h-16 w-full rounded-[6px] border px-2 py-1 text-left transition-colors hover:ring-2 hover:ring-indigo-300", statusTone(node.status))}
                                onClick={() => navigate(`/runs/${run.id}`)}
                                title={`${node.node_id}: ${node.status}`}
                              >
                                <span className="block truncate font-semibold">{statusLabel(node.status)}</span>
                                <span className="mt-0.5 block truncate text-[11px] opacity-80">{formatDuration(node.started_at, node.finished_at)}</span>
                                <span className="mt-0.5 block truncate text-[11px] opacity-80">R{node.retry_count} / A{artifactCount}</span>
                              </button>
                            ) : (
                              <div className="h-16 rounded-[6px] border border-dashed border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/40" aria-label={`No ${nodeType} node for ${run.id}`} />
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
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
              <select aria-label="Rows per page" className="h-7 rounded border border-slate-200 bg-white px-2 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
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
