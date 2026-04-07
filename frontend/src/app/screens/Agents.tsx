import React from "react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { agents } from "../data/agents";
import { cn } from "../lib/utils";
import { CheckCircle2, AlertTriangle, AlertCircle, Bot } from "lucide-react";

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

const healthIcon = {
  healthy: <CheckCircle2 size={14} className="text-emerald-500" />,
  degraded: <AlertTriangle size={14} className="text-amber-500" />,
  offline: <AlertCircle size={14} className="text-red-500" />,
};

const healthVariant: Record<string, "success" | "warning" | "danger"> = {
  healthy: "success",
  degraded: "warning",
  offline: "danger",
};

export default function Agents() {
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

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 shadow-sm p-5 hover:shadow-md transition-shadow"
              style={{ borderLeftColor: agentTypeColors[agent.type], borderLeftWidth: 3 }}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="size-9 rounded-[6px] flex items-center justify-center" style={{ backgroundColor: agentTypeColors[agent.type] + "20" }}>
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
      </div>
    </AppShell>
  );
}

