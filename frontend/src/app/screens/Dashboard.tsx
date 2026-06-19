import React, { useMemo } from "react";
import { useNavigate } from "react-router";
import {
  ArrowRight,
  BarChart2,
  Bot,
  ChevronDown,
  Database,
  GitBranch,
  Play,
  TrendingUp,
} from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Badge, RunStatusBadge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import { useDataSources } from "../hooks/useDataSources";
import { useAgentCatalog } from "../hooks/useDiscovery";
import { useRuns } from "../hooks/useRuns";
import { useWorkflows } from "../hooks/useWorkflows";
import { formatDuration, formatRelativeTime } from "../utils/time";

function StatCard({
  label,
  value,
  delta,
  icon,
  iconColor,
}: {
  label: string;
  value: string | number;
  delta?: string;
  icon: React.ReactNode;
  iconColor: string;
}) {
  return (
    <div className="rounded-[8px] border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="mb-3 flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">{label}</p>
        <div className={`size-8 rounded-[6px] ${iconColor} flex items-center justify-center`}>{icon}</div>
      </div>
      <p className="tabular-nums text-2xl font-semibold text-slate-900 dark:text-slate-50">{value}</p>
      {delta ? (
        <p className="mt-1 flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
          <TrendingUp size={11} />
          {delta}
        </p>
      ) : null}
    </div>
  );
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, workspaceId } = useAuth();
  const { data: runsData, isLoading: loadingRuns, error: runsError, refetch: fetchRuns } = useRuns(workspaceId);
  const workflowsQuery = useWorkflows(workspaceId);
  const dataSourcesQuery = useDataSources(workspaceId);
  const agentsQuery = useAgentCatalog(workspaceId);

  const runs = runsData?.items ?? [];
  const workflows = workflowsQuery.data?.items ?? [];
  const dataSources = dataSourcesQuery.data?.items ?? [];
  const agents = agentsQuery.data?.results ?? [];
  const workflowHealth = useMemo(() => {
    return workflows.reduce(
      (acc, workflow) => {
        const status = workflow.validation_summary?.status ?? "safe";
        if (status === "invalid") acc.invalid += 1;
        else if (status === "advisory") acc.advisory += 1;
        else acc.safe += 1;
        return acc;
      },
      { safe: 0, advisory: 0, invalid: 0 },
    );
  }, [workflows]);

  const recentRuns = useMemo(() => runs.slice(0, 5), [runs]);
  const activityRuns = useMemo(() => runs.slice(0, 8), [runs]);
  const activeRunsCount = runs.filter((run) => ["running", "pending"].includes(run.status)).length;
  const reportsLast30Days = runs.filter((run) => {
    if (run.status !== "success" || !run.created_at) return false;
    const createdAt = new Date(run.created_at).getTime();
    const thirtyDaysAgo = Date.now() - 30 * 24 * 60 * 60 * 1000;
    return createdAt >= thirtyDaysAgo;
  }).length;
  const firstName = user?.email?.split("@")[0] ?? user?.sub?.split("@")[0] ?? "there";

  return (
    <AppShell>
      <div className="mx-auto max-w-[1280px] space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "20px", fontWeight: 600 }}>
              {getGreeting()}, {firstName}
            </h1>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
              Here is what is happening in your workspace today.
            </p>
          </div>
          <span className="hidden items-center gap-1.5 rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 dark:border-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300 sm:inline-flex">
            {workspaceId ?? "--"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatCard
            label="Active Runs"
            value={loadingRuns ? "…" : activeRunsCount}
            icon={<Play size={16} className="text-indigo-600" />}
            iconColor="bg-indigo-50 dark:bg-indigo-900/30"
          />
          <StatCard
            label="Workflows"
            value={workflowsQuery.isLoading ? "…" : workflows.length}
            icon={<GitBranch size={16} className="text-violet-600" />}
            iconColor="bg-violet-50 dark:bg-violet-900/30"
          />
          <StatCard
            label="Agents"
            value={agentsQuery.isLoading ? "…" : agents.length}
            icon={<Bot size={16} className="text-emerald-600" />}
            iconColor="bg-emerald-50 dark:bg-emerald-900/30"
          />
          <StatCard
            label="Data Sources"
            value={dataSourcesQuery.isLoading ? "…" : dataSources.length}
            delta={!dataSourcesQuery.isLoading && dataSources.length > 0 ? `${dataSources.length} connected` : undefined}
            icon={<Database size={16} className="text-sky-600" />}
            iconColor="bg-sky-50 dark:bg-sky-900/30"
          />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          <div className="overflow-hidden rounded-[8px] border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900 lg:col-span-3">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Recent Runs</h2>
              <button
                onClick={() => navigate("/runs")}
                className="flex items-center gap-1 text-xs text-indigo-600 hover:underline dark:text-indigo-400"
              >
                View All Runs <ArrowRight size={12} />
              </button>
            </div>

            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              <AsyncState
                isLoading={loadingRuns}
                error={runsError?.message ?? null}
                isEmpty={!loadingRuns && !runsError && recentRuns.length === 0}
                emptyTitle="No runs yet"
                emptyDescription="Trigger your first workflow run to populate this list."
                className="px-5 py-6"
                onRetry={() => fetchRuns()}
              >
                {recentRuns.map((run) => (
                  <div
                    key={run.id}
                    className="flex cursor-pointer items-center gap-3 px-5 py-3 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                    onClick={() => navigate(`/runs/${run.id}`)}
                  >
                    <RunStatusBadge status={run.status} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">{run.flow_key}</p>
                      <p className="truncate text-xs text-slate-400">{run.id}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-xs text-slate-400">{formatRelativeTime(run.started_at)}</p>
                      <p className="tabular-nums text-xs text-slate-500">{formatDuration(run.started_at, run.finished_at)}</p>
                    </div>
                  </div>
                ))}
              </AsyncState>
            </div>
          </div>

          <div className="rounded-[8px] border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900 lg:col-span-2">
            <h2 className="mb-4 text-sm font-semibold text-slate-900 dark:text-slate-100">Quick Actions</h2>
            <div className="space-y-2">
              {[
                { label: "New Workflow", icon: <GitBranch size={15} />, to: "/workflows" },
                { label: "Trigger Run", icon: <Play size={15} />, to: "/runs" },
                { label: "Browse Data Sources", icon: <Database size={15} />, to: "/data-sources" },
                { label: `Reports (30d): ${reportsLast30Days}`, icon: <BarChart2 size={15} />, to: "/reports" },
              ].map((action) => (
                <Button
                  key={action.label}
                  variant="secondary"
                  size="md"
                  fullWidth
                  className="justify-start"
                  leadingIcon={action.icon}
                  onClick={() => navigate(action.to)}
                >
                  {action.label}
                </Button>
              ))}
            </div>
            <div className="mt-5 border-t border-slate-100 pt-4 dark:border-slate-800">
              <div className="mb-2 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Workflow Health</p>
                <button
                  type="button"
                  className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
                  onClick={() => navigate("/workflows")}
                >
                  Review
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge variant="success" size="sm">Safe: {workflowHealth.safe}</Badge>
                <Badge variant="warning" size="sm">Advisory: {workflowHealth.advisory}</Badge>
                <Badge variant="danger" size="sm">Invalid: {workflowHealth.invalid}</Badge>
              </div>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-[8px] border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-800">
            <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Activity Feed</h2>
          </div>

          <div className="space-y-0 px-5 py-4">
            <AsyncState
              isLoading={loadingRuns}
              error={runsError?.message ?? null}
              isEmpty={!loadingRuns && !runsError && activityRuns.length === 0}
              emptyTitle="No activity yet"
              emptyDescription="Run a workflow to start building your activity feed."
              className="py-4"
              onRetry={() => fetchRuns()}
            >
              {activityRuns.map((run, idx) => (
                <div key={run.id} className="relative flex gap-3">
                  {idx < activityRuns.length - 1 ? (
                    <div className="absolute bottom-0 left-4 top-8 w-px bg-slate-100 dark:bg-slate-800" />
                  ) : null}
                  <div className="relative z-10 mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-50 dark:bg-indigo-900/40">
                    <Play size={12} className="text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div className="min-w-0 flex-1 pb-4">
                    <p className="text-sm text-slate-700 dark:text-slate-300">
                      <span className="font-medium">{run.flow_key}</span>{" "}
                      <span className="text-slate-500 dark:text-slate-400">status: {run.status}</span>
                    </p>
                    <p className="mt-0.5 text-xs text-slate-400">{formatRelativeTime(run.created_at)}</p>
                  </div>
                </div>
              ))}
            </AsyncState>
          </div>

          <div className="border-t border-slate-100 px-5 py-3 dark:border-slate-800">
            <button className="flex items-center gap-1 text-xs text-indigo-600 hover:underline dark:text-indigo-400">
              Load More <ChevronDown size={12} />
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
