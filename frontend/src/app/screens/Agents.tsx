import { useMemo } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import { useAgentCatalog, useAgentExecutionSummary } from "../hooks/useDiscovery";
import { Activity, AlertTriangle, Bot, Clock3, Package, RotateCcw, Terminal } from "lucide-react";

const agentTypeColors: Record<string, string> = {
  iac: "#f97316",
  container: "#06b6d4",
  cicd: "#8b5cf6",
  eda: "#10b981",
  ml: "#6366f1",
  hitl: "#f59e0b",
  strategic: "#ec4899",
  control: "#64748b",
};

const healthVariant: Record<string, "success" | "warning" | "danger"> = {
  healthy: "success",
  degraded: "warning",
  offline: "danger",
};

type AgentType = keyof typeof agentTypeColors;

function mapCategoryToType(category?: string): AgentType {
  switch (category) {
    case "eda":
      return "eda";
    case "machine_learning":
      return "ml";
    case "human_in_the_loop":
      return "hitl";
    case "strategy":
      return "strategic";
    case "orchestration":
      return "control";
    case "infrastructure":
      return "iac";
    case "ci_cd":
      return "cicd";
    default:
      return "control";
  }
}

function asNumber(value: unknown): number {
  const parsed = typeof value === "number" ? value : Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

function objectKeyCount(value: unknown): number {
  return value && typeof value === "object" && !Array.isArray(value) ? Object.keys(value).length : 0;
}

function formatDurationMs(value: number | null): string {
  if (value === null) return "--";
  if (value < 1000) return `${value} ms`;
  return `${(value / 1000).toFixed(1)} s`;
}

export default function Agents() {
  const { workspaceId } = useAuth();
  const agentsQuery = useAgentCatalog(workspaceId);
  const executionQuery = useAgentExecutionSummary(workspaceId);
  const agents = (agentsQuery.data?.results ?? []).map((agent, index) => ({
    id: `${agent.name}-${index}`,
    name: agent.name,
    type: mapCategoryToType(agent.category),
    status:
      agent.status === "degraded" || agent.status === "offline"
        ? agent.status
        : "healthy",
    description: agent.description,
  }));
  const healthy = agents.filter((a) => a.status === "healthy").length;
  const total = agents.length;
  const executionSummary = useMemo(() => {
    const nodeSection = executionQuery.data?.sections.find((item) => item.resource_key === "run.nodes");
    const traceSection = executionQuery.data?.sections.find((item) => item.resource_key === "agent.traces");
    const records = nodeSection?.records ?? [];
    const traceRecords = traceSection?.records ?? [];
    const byType = new Map<
      string,
      { nodeType: string; executions: number; failures: number; retries: number; artifacts: number; durationMs: number; durationCount: number }
    >();
    const failureModes = new Map<string, number>();
    let failures = 0;
    let retries = 0;
    let artifacts = 0;
    for (const record of records) {
      const nodeType = typeof record.node_type === "string" ? record.node_type : "unknown";
      const status = typeof record.status === "string" ? record.status.toLowerCase() : "";
      const retryCount = asNumber(record.retry_count);
      const artifactCount = asStringArray(record.produced_artifact_ids).length;
      const current = byType.get(nodeType) ?? {
        nodeType,
        executions: 0,
        failures: 0,
        retries: 0,
        artifacts: 0,
        durationMs: 0,
        durationCount: 0,
      };
      current.executions += 1;
      current.retries += retryCount;
      current.artifacts += artifactCount;
      if (["failed", "error", "cancelled"].includes(status)) {
        current.failures += 1;
        failures += 1;
        const errorKey = typeof record.error === "string" && record.error.trim() ? record.error.trim() : `${nodeType} ${status}`;
        failureModes.set(errorKey, (failureModes.get(errorKey) ?? 0) + 1);
      }
      retries += retryCount;
      artifacts += artifactCount;
      byType.set(nodeType, current);
    }
    let toolCalls = 0;
    let tokenFields = 0;
    let costFields = 0;
    let evaluationFields = 0;
    let versionFields = 0;
    let traceDurationMs = 0;
    let traceDurationCount = 0;
    for (const trace of traceRecords) {
      const nodeType = typeof trace.node_type === "string" ? trace.node_type : "unknown";
      const status = typeof trace.status === "string" ? trace.status.toLowerCase() : "";
      const duration = asNumber(trace.duration_ms);
      const current = byType.get(nodeType) ?? {
        nodeType,
        executions: 0,
        failures: 0,
        retries: 0,
        artifacts: 0,
        durationMs: 0,
        durationCount: 0,
      };
      toolCalls += asNumber(trace.tool_call_count);
      const artifactCount = asStringArray(trace.artifact_ids).length;
      artifacts += artifactCount;
      current.artifacts += artifactCount;
      if (duration > 0) {
        traceDurationMs += duration;
        traceDurationCount += 1;
        current.durationMs += duration;
        current.durationCount += 1;
      }
      tokenFields += objectKeyCount(trace.token_usage);
      costFields += objectKeyCount(trace.cost_summary);
      evaluationFields += objectKeyCount(trace.evaluation_summary);
      versionFields += objectKeyCount(trace.version_metadata);
      if (["failed", "error", "cancelled"].includes(status)) {
        const errorKey =
          typeof trace.error_summary === "string" && trace.error_summary.trim()
            ? trace.error_summary.trim()
            : `${nodeType} ${status}`;
        failureModes.set(errorKey, (failureModes.get(errorKey) ?? 0) + 1);
      }
      byType.set(nodeType, current);
    }
    const totalExecutions = records.length;
    const successRate = totalExecutions > 0 ? Math.round(((totalExecutions - failures) / totalExecutions) * 100) : 0;
    return {
      records,
      traceRecords,
      totalExecutions,
      failures,
      retries,
      artifacts,
      toolCalls,
      tokenFields,
      costFields,
      evaluationFields,
      versionFields,
      successRate,
      averageDurationMs: traceDurationCount > 0 ? Math.round(traceDurationMs / traceDurationCount) : null,
      byType: Array.from(byType.values())
        .sort((a, b) => b.executions - a.executions || b.artifacts - a.artifacts)
        .slice(0, 5),
      failureModes: Array.from(failureModes.entries()).map(([message, count]) => ({ message, count })).slice(0, 3),
      status: nodeSection?.status ?? traceSection?.status ?? "empty",
      message: nodeSection?.message ?? traceSection?.message,
    };
  }, [executionQuery.data]);

  return (
    <AppShell>
      <div className="p-6 max-w-[1280px] mx-auto space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
              Agents
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              {healthy} healthy / {total} total agents active in your workspace.
            </p>
          </div>
        </div>

        <div className="rounded-[8px] border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Agent Cockpit</h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {executionSummary.totalExecutions > 0
                  ? `${executionSummary.totalExecutions} node execution records from platform runs.`
                  : "No execution traces have been recorded for this workspace yet."}
              </p>
            </div>
            <Badge variant={executionSummary.failures > 0 ? "warning" : "success"} size="sm">
              {executionSummary.status}
            </Badge>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-6">
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Activity size={16} className="text-indigo-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Executions</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.totalExecutions}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Activity size={16} className="text-emerald-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Success Rate</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.successRate}%</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <AlertTriangle size={16} className={executionSummary.failures > 0 ? "text-amber-500" : "text-emerald-500"} />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Failures</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.failures}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <RotateCcw size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Retries</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.retries}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Terminal size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Tool Calls</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.toolCalls}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Package size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Artifacts</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.artifacts}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Clock3 size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Avg Trace</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{formatDurationMs(executionSummary.averageDurationMs)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Terminal size={16} className="text-indigo-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Token Fields</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.tokenFields}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Activity size={16} className="text-emerald-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Cost Fields</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{executionSummary.costFields}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-[6px] border border-slate-200 px-3 py-2 dark:border-slate-700">
              <Package size={16} className="text-slate-500" />
              <div>
                <p className="text-[10px] font-medium uppercase text-slate-400">Eval/Version</p>
                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {executionSummary.evaluationFields}/{executionSummary.versionFields}
                </p>
              </div>
            </div>
          </div>
          {executionSummary.byType.length > 0 ? (
            <div className="mt-3 overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-400">
                    <th className="border-b border-slate-200 py-1 pr-2 font-medium dark:border-slate-700">Node type</th>
                    <th className="border-b border-slate-200 py-1 pr-2 font-medium dark:border-slate-700">Executions</th>
                    <th className="border-b border-slate-200 py-1 pr-2 font-medium dark:border-slate-700">Failures</th>
                    <th className="border-b border-slate-200 py-1 pr-2 font-medium dark:border-slate-700">Retries</th>
                    <th className="border-b border-slate-200 py-1 pr-2 font-medium dark:border-slate-700">Artifacts</th>
                    <th className="border-b border-slate-200 py-1 pr-2 font-medium dark:border-slate-700">Avg Trace</th>
                  </tr>
                </thead>
                <tbody>
                  {executionSummary.byType.map((item) => (
                    <tr key={item.nodeType} className="text-slate-600 dark:text-slate-300">
                      <td className="border-b border-slate-100 py-1 pr-2 font-medium dark:border-slate-800">{item.nodeType}</td>
                      <td className="border-b border-slate-100 py-1 pr-2 dark:border-slate-800">{item.executions}</td>
                      <td className="border-b border-slate-100 py-1 pr-2 dark:border-slate-800">{item.failures}</td>
                      <td className="border-b border-slate-100 py-1 pr-2 dark:border-slate-800">{item.retries}</td>
                      <td className="border-b border-slate-100 py-1 pr-2 dark:border-slate-800">{item.artifacts}</td>
                      <td className="border-b border-slate-100 py-1 pr-2 dark:border-slate-800">
                        {formatDurationMs(item.durationCount > 0 ? Math.round(item.durationMs / item.durationCount) : null)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
          {executionSummary.failureModes.length > 0 ? (
            <div className="mt-3 rounded-[6px] border border-amber-200 bg-amber-50 px-3 py-2 dark:border-amber-900 dark:bg-amber-950/30">
              <p className="text-[10px] font-medium uppercase text-amber-700 dark:text-amber-300">Top Failure Signals</p>
              <div className="mt-2 space-y-1 text-xs text-amber-800 dark:text-amber-200">
                {executionSummary.failureModes.map((item) => (
                  <p key={item.message}>
                    {item.count}x {item.message}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <AsyncState
          isLoading={agentsQuery.isLoading}
          error={agentsQuery.error instanceof Error ? agentsQuery.error.message : null}
          isEmpty={!agentsQuery.isLoading && agents.length === 0}
          emptyTitle="No agents discovered"
          emptyDescription="Agent discovery is available, but no registered agents were returned for this workspace."
          onRetry={() => {
            void agentsQuery.refetch();
          }}
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="rounded-[8px] border border-slate-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900"
                style={{ borderLeftColor: agentTypeColors[agent.type], borderLeftWidth: 3 }}
              >
                <div className="mb-3 flex items-start justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="flex size-9 items-center justify-center rounded-[6px]" style={{ backgroundColor: agentTypeColors[agent.type] + "20" }}>
                      <Bot size={18} style={{ color: agentTypeColors[agent.type] }} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{agent.name}</p>
                      <p className="text-[10px] font-medium uppercase tracking-wide" style={{ color: agentTypeColors[agent.type] }}>
                        {agent.type}
                      </p>
                    </div>
                  </div>
                  <Badge variant={healthVariant[agent.status]} size="sm" dot>
                    {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
                  </Badge>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{agent.description}</p>
              </div>
            ))}
          </div>
        </AsyncState>
      </div>
    </AppShell>
  );
}

