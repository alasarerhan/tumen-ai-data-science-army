import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import { useAgentCatalog } from "../hooks/useDiscovery";
import { Bot } from "lucide-react";

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

export default function Agents() {
  const { workspaceId } = useAuth();
  const agentsQuery = useAgentCatalog(workspaceId);
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

