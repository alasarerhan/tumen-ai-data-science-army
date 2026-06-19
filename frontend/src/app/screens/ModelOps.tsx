import { useMemo } from "react";
import { Link } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, LineChart, RefreshCw, Rocket, ShieldCheck } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { AsyncState } from "../components/ui/async-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";
import { getModelOpsSummary, type ModelRegistryEntry, type ModelMonitorSnapshot } from "../api/modelops";
import { formatRelativeTime } from "../utils/time";

function statusVariant(status: string): "neutral" | "success" | "warning" | "danger" | "info" {
  if (status === "critical") return "danger";
  if (status === "warning") return "warning";
  if (status === "ok" || status === "linked" || status === "artifact_backed") return "success";
  if (status === "candidate_detection" || status === "snapshot") return "info";
  return "neutral";
}

function modelLabel(model: ModelRegistryEntry) {
  return `${model.version} / ${model.stage}`;
}

function monitorLabel(monitor: ModelMonitorSnapshot) {
  return `${monitor.kind} / ${monitor.freshness}`;
}

export default function ModelOps() {
  const { workspaceId } = useAuth();
  const summaryQuery = useQuery({
    queryKey: ["modelops-summary", workspaceId],
    queryFn: () => {
      if (!workspaceId) {
        throw new Error("Workspace is required");
      }
      return getModelOpsSummary(workspaceId);
    },
    enabled: Boolean(workspaceId),
  });
  const registry = useMemo(() => summaryQuery.data?.registry ?? [], [summaryQuery.data?.registry]);
  const monitors = useMemo(() => summaryQuery.data?.monitors ?? [], [summaryQuery.data?.monitors]);
  const retrainCandidates = useMemo(
    () => summaryQuery.data?.retrain_candidates ?? [],
    [summaryQuery.data?.retrain_candidates],
  );
  const metrics = summaryQuery.data?.metrics ?? {
    registered_models: 0,
    monitor_snapshots: 0,
    retrain_candidates: 0,
    deployments: 0,
  };
  const status = summaryQuery.data?.status;
  const latestModel = useMemo(() => registry[0] ?? null, [registry]);

  return (
    <AppShell>
      <div className="mx-auto max-w-[1360px] space-y-5 p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">ModelOps</p>
            <h1 className="mt-1 text-3xl font-semibold text-slate-900 dark:text-slate-50">Model Registry & Monitoring</h1>
            <p className="mt-1 max-w-3xl text-sm text-slate-500 dark:text-slate-400">
              Artifact-backed model inventory, monitor snapshots, retrain candidates, and deployment readiness state.
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<RefreshCw size={14} />}
            onClick={() => {
              void summaryQuery.refetch();
            }}
          >
            Refresh
          </Button>
        </div>

        <AsyncState
          isLoading={summaryQuery.isLoading}
          error={summaryQuery.error instanceof Error ? summaryQuery.error.message : null}
          isEmpty={!summaryQuery.isLoading && registry.length === 0 && monitors.length === 0}
          emptyTitle="No model artifacts yet"
          emptyDescription="ModelOps will populate after model training and evaluation artifacts are produced."
          onRetry={() => {
            void summaryQuery.refetch();
          }}
        >
          <div className="grid gap-4 md:grid-cols-4">
            {[
              { label: "Registered Models", value: metrics.registered_models, icon: <ShieldCheck size={16} /> },
              { label: "Monitor Snapshots", value: metrics.monitor_snapshots, icon: <LineChart size={16} /> },
              { label: "Retrain Candidates", value: metrics.retrain_candidates, icon: <AlertTriangle size={16} /> },
              { label: "Deployments", value: metrics.deployments, icon: <Rocket size={16} /> },
            ].map((item) => (
              <div key={item.label} className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                  {item.icon}
                  {item.label}
                </div>
                <p className="mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-50">{item.value}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
            <section className="rounded-md border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3 dark:border-slate-800">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Registry</h2>
                  <p className="text-xs text-slate-500">Models promoted from workflow artifacts.</p>
                </div>
                {status ? <Badge variant={statusVariant(status.registry)}>{status.registry}</Badge> : null}
              </div>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm dark:divide-slate-800">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-950">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium">Model</th>
                      <th className="px-4 py-2 text-left font-medium">Monitoring</th>
                      <th className="px-4 py-2 text-left font-medium">Drift</th>
                      <th className="px-4 py-2 text-left font-medium">Performance</th>
                      <th className="px-4 py-2 text-left font-medium">Run</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {registry.map((model) => (
                      <tr key={model.model_id}>
                        <td className="px-4 py-3">
                          <p className="font-medium text-slate-900 dark:text-slate-50">{modelLabel(model)}</p>
                          <p className="mt-0.5 font-mono text-xs text-slate-400">{model.artifact_id}</p>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={statusVariant(model.monitoring_status)}>{model.monitoring_status}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={statusVariant(model.drift_status)}>{model.drift_status}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={statusVariant(model.performance_status)}>{model.performance_status}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          {model.workflow_run_id ? (
                            <Link className="text-xs font-medium text-indigo-600 hover:underline" to={`/runs/${model.workflow_run_id}`}>
                              Open run
                            </Link>
                          ) : (
                            <span className="text-xs text-slate-400">--</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            <section className="rounded-md border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Readiness</h2>
                  <p className="text-xs text-slate-500">Deployment handoff is explicit, not inferred.</p>
                </div>
                {status ? <Badge variant={statusVariant(status.deployment)}>{status.deployment}</Badge> : null}
              </div>
              <div className="mt-4 space-y-3 text-sm text-slate-600 dark:text-slate-300">
                <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-950">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Latest Model</p>
                  <p className="mt-1 font-medium text-slate-900 dark:text-slate-50">{latestModel ? modelLabel(latestModel) : "--"}</p>
                </div>
                <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-950">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Monitoring Source</p>
                  <p className="mt-1">{status?.monitoring ?? "not_configured"}</p>
                </div>
                <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-950">
                  <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Retraining</p>
                  <p className="mt-1">{status?.retraining ?? "not_configured"}</p>
                </div>
              </div>
            </section>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className="rounded-md border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
              <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800">
                <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Monitor Snapshots</h2>
                <p className="text-xs text-slate-500">Evaluation, metrics, and drift artifacts tied to model runs.</p>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {monitors.map((monitor) => (
                  <div key={monitor.monitor_id} className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-3">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-slate-50">{monitorLabel(monitor)}</p>
                      <p className="mt-0.5 text-xs text-slate-400">{formatRelativeTime(monitor.created_at)}</p>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-2">
                      <Badge variant={statusVariant(monitor.drift_status)}>drift {monitor.drift_status}</Badge>
                      <Badge variant={statusVariant(monitor.performance_status)}>perf {monitor.performance_status}</Badge>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-md border border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
              <div className="border-b border-slate-200 px-4 py-3 dark:border-slate-800">
                <h2 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Retrain Candidates</h2>
                <p className="text-xs text-slate-500">Candidates are planned through governed workflow actions.</p>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {retrainCandidates.length > 0 ? (
                  retrainCandidates.map((candidate) => (
                    <div key={candidate.model_id} className="px-4 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-medium text-slate-900 dark:text-slate-50">{candidate.version}</p>
                        <Badge variant={statusVariant(candidate.action_state)}>{candidate.action_state}</Badge>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Badge variant={statusVariant(candidate.drift_status)}>drift {candidate.drift_status}</Badge>
                        <Badge variant={statusVariant(candidate.performance_status)}>perf {candidate.performance_status}</Badge>
                      </div>
                      <p className="mt-2 text-xs text-slate-500">{candidate.suggested_workflow}</p>
                    </div>
                  ))
                ) : (
                  <div className="flex min-h-32 items-center justify-center px-4 py-8 text-center text-sm text-slate-500">
                    <div>
                      <Activity className="mx-auto mb-2 text-slate-300" size={22} />
                      No retrain candidates detected.
                    </div>
                  </div>
                )}
              </div>
            </section>
          </div>
        </AsyncState>
      </div>
    </AppShell>
  );
}
