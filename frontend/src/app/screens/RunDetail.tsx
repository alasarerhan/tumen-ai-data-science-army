import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ChevronLeft, Copy, Download, ExternalLink, FileText, RefreshCw, Terminal, XCircle } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { RunStatusBadge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import type { Artifact } from "../api/artifacts";
import { useAuth } from "../context/AuthContext";
import { buildRunLogsStreamUrl } from "../api/logs";
import { buildPrefectRunUrl } from "../api/runs";
import { useEventSource } from "../hooks/useEventSource";
import { useArtifactAccess, useRunArtifacts } from "../hooks/useArtifacts";
import { useCancelRun, useRetryRun, useRun, useRuns } from "../hooks/useRuns";
import { useWorkflows } from "../hooks/useWorkflows";
import { formatDuration, formatRelativeTime } from "../utils/time";
import type { Run } from "../api/runs";

const TABS = ["Overview", "Logs", "Artifacts", "Strategy Report"] as const;
type Tab = (typeof TABS)[number];

type LogEvent = {
  level?: string;
  time?: string;
  ts?: string;
  msg?: string;
  timestamp?: string;
  message?: string;
};

function formatDateTime(value: string | null): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function formatLogTime(value?: string): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString();
}

function normalizeRunStatus(status: string | null | undefined): string {
  return (status ?? "").trim().toLowerCase();
}

function formatParameterLabel(key: string): string {
  return key
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (value) => value.toUpperCase());
}

function buildStrategyReport(run: Run | null, artifacts: Artifact[]) {
  const normalizedStatus = normalizeRunStatus(run?.status);
  const parameters = Object.entries(run?.parameters ?? {}).filter(([key, value]) => {
    return key !== "requested_by" && value !== null && value !== undefined && value !== "";
  });
  const artifactCounts = artifacts.reduce<Record<string, number>>((acc, artifact) => {
    acc[artifact.kind] = (acc[artifact.kind] ?? 0) + 1;
    return acc;
  }, {});
  const artifactLines = Object.entries(artifactCounts).map(([kind, count]) => `${count} ${kind}`);
  const primaryObjective = parameters.find(([key]) =>
    ["prompt", "goal", "question", "dataset", "dataset_name", "report_type"].includes(key),
  );

  let headline = "Run context is still materializing.";
  let summary = "The run has started, but there is not enough execution data yet to assemble a full strategy readout.";
  let nextActions = [
    "Wait for the run to emit logs and artifacts before reviewing downstream outputs.",
    "Use the monitor view if you need real-time intervention on this execution.",
  ];

  if (normalizedStatus === "success" || normalizedStatus === "completed") {
    headline = "Execution completed and outputs are ready for review.";
    summary = artifactLines.length
      ? `The run finished successfully and produced ${artifactLines.join(", ")}. Review the generated assets before promoting this workflow result.`
      : "The run finished successfully but did not persist any artifacts. Validate the workflow output path before considering it release-ready.";
    nextActions = artifactLines.length
      ? [
          "Open the highest-value artifacts and validate that each output matches the intended business question.",
          "Use the reports page or downstream consumers to publish approved outputs.",
        ]
      : [
          "Inspect the workflow definition and persistence settings to ensure outputs are being registered.",
          "Re-run only after confirming artifact registration or storage configuration.",
        ];
  } else if (normalizedStatus === "failed") {
    headline = "Execution failed before producing a stable delivery.";
    summary = artifactLines.length
      ? `The run failed after producing partial output: ${artifactLines.join(", ")}. Treat all generated assets as provisional until the failure is resolved.`
      : "The run failed without any persisted artifact payloads. Use logs to identify the failing stage and retry only after addressing the root cause.";
    nextActions = [
      "Inspect the live log stream to isolate the first actionable error.",
      "Re-run after correcting the failing dependency, configuration, or upstream data issue.",
    ];
  }

  const executionSignals = [
    `Status: ${run?.status ?? "--"}`,
    `Flow key: ${run?.flow_key ?? "--"}`,
    primaryObjective ? `${formatParameterLabel(primaryObjective[0])}: ${String(primaryObjective[1])}` : "Objective: No explicit business objective captured in run parameters.",
    artifactLines.length ? `Artifacts: ${artifactLines.join(", ")}` : "Artifacts: None registered yet.",
  ];

  if (run?.started_at) {
    executionSignals.push(`Started: ${formatDateTime(run.started_at)}`);
  }
  if (run?.finished_at) {
    executionSignals.push(`Finished: ${formatDateTime(run.finished_at)}`);
  }

  const parameterHighlights = parameters.slice(0, 4).map(([key, value]) => {
    return `${formatParameterLabel(key)}: ${typeof value === "string" ? value : JSON.stringify(value)}`;
  });

  if (parameterHighlights.length === 0) {
    parameterHighlights.push("No additional run parameters were captured for this execution.");
  }

  return {
    headline,
    summary,
    executionSignals,
    nextActions,
    parameterHighlights,
  };
}

export default function RunDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { workspaceId } = useAuth();

  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [runError, setRunError] = useState<string | null>(null);
  const [artifactsError, setArtifactsError] = useState<string | null>(null);
  const runQuery = useRun(id, workspaceId);
  const runsQuery = useRuns(workspaceId);
  const workflowsQuery = useWorkflows(workspaceId);
  const artifactsQuery = useRunArtifacts(id, workspaceId, activeTab === "Artifacts" || activeTab === "Strategy Report");
  const cancelRunMutation = useCancelRun(workspaceId);
  const retryRunMutation = useRetryRun(workspaceId);
  const artifactAccessMutation = useArtifactAccess(workspaceId);

  const run = runQuery.data ?? null;
  const loadingRun = runQuery.isLoading || runsQuery.isLoading;
  const relatedRuns = useMemo<Run[]>(
    () => (runsQuery.data?.items ?? []).filter((item) => item.id !== id).slice(0, 5),
    [runsQuery.data, id],
  );
  const artifacts = artifactsQuery.data?.items ?? [];
  const loadingArtifacts = artifactsQuery.isLoading;
  const normalizedRunStatus = useMemo(() => normalizeRunStatus(run?.status), [run?.status]);
  const prefectRunUrl = useMemo(() => buildPrefectRunUrl(run?.prefect_flow_run_id), [run?.prefect_flow_run_id]);
  const sourceWorkflow = useMemo(() => {
    const workflows = workflowsQuery.data?.items ?? [];
    if (!run?.flow_key) return null;
    return (
      workflows.find((workflow) => workflow.id === run.flow_key || workflow.name === run.flow_key) ?? null
    );
  }, [run?.flow_key, workflowsQuery.data?.items]);
  const workflowValidation = sourceWorkflow?.validation_summary ?? null;
  const strategyReport = useMemo(() => buildStrategyReport(run, artifacts), [artifacts, run]);

  useEffect(() => {
    if (runQuery.error) {
      setRunError(runQuery.error instanceof Error ? runQuery.error.message : "Failed to load run details");
      return;
    }
    if (runsQuery.error) {
      setRunError(runsQuery.error instanceof Error ? runsQuery.error.message : "Failed to load related runs");
      return;
    }
    setRunError(null);
  }, [runQuery.error, runsQuery.error]);

  useEffect(() => {
    if (!artifactsQuery.error) {
      setArtifactsError(null);
      return;
    }
    setArtifactsError(
      artifactsQuery.error instanceof Error ? artifactsQuery.error.message : "Failed to load artifacts",
    );
  }, [artifactsQuery.error]);

  const logsUrl = useMemo(() => {
    if (!workspaceId || !id || activeTab !== "Logs") return null;
    return buildRunLogsStreamUrl(id, workspaceId);
  }, [activeTab, id, workspaceId]);

  const logsStream = useEventSource<LogEvent>({
    url: logsUrl,
    enabled: Boolean(logsUrl),
  });

  useEffect(() => {
    if (activeTab === "Logs") {
      logsStream.clear();
    }
  }, [activeTab, id, logsStream]);

  const visibleLogs = logsStream.events
    .map((event) => ({
      level: event.level ?? "INFO",
      time: event.time ?? formatLogTime(event.timestamp ?? event.ts),
      message: event.msg ?? event.message ?? "",
    }))
    .filter((event) => event.message && event.message !== "__STREAM_END__");

  const isRunning = normalizedRunStatus === "running";

  const handleCancel = async () => {
    if (!id || !workspaceId) return;
    try {
      await cancelRunMutation.mutateAsync(id);
      await Promise.all([runQuery.refetch(), runsQuery.refetch()]);
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Failed to cancel run");
    }
  };

  const handleRetry = async () => {
    if (!id || !workspaceId) return;
    try {
      await retryRunMutation.mutateAsync(id);
      navigate("/runs");
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Failed to retry run");
    }
  };

  const handleArtifactOpen = async (artifactId: string) => {
    if (!workspaceId) return;
    try {
      const access = await artifactAccessMutation.mutateAsync(artifactId);
      if (access?.delivery?.url) {
        const url = new URL(access.delivery.url);
        const allowedProtocols = ['http:', 'https:'];
        if (!allowedProtocols.includes(url.protocol)) {
          throw new Error('Invalid URL protocol');
        }
        window.open(access.delivery.url, "_blank", "noopener,noreferrer");
      }
    } catch (err: unknown) {
      setArtifactsError(err instanceof Error ? err.message : "Failed to open artifact");
    }
  };

  return (
    <AppShell>
      <div className="grid h-full grid-cols-12">
        <main className="col-span-9 min-h-0 overflow-auto border-r border-slate-200 p-6">
          <div className="mx-auto max-w-4xl space-y-5">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <button type="button" onClick={() => navigate("/runs")} className="inline-flex items-center gap-1 hover:text-slate-700">
                <ChevronLeft size={14} /> Runs
              </button>
              <span>/</span>
              <code className="text-xs text-slate-600">{id ?? "--"}</code>
            </div>

            <AsyncState
              isLoading={loadingRun}
              error={runError}
              isEmpty={!loadingRun && !run}
              emptyTitle="Run not found"
              emptyDescription="The selected run may have been removed."
              onRetry={() => {
                void Promise.all([runQuery.refetch(), runsQuery.refetch()]);
              }}
            >
              <div className="space-y-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <h1 className="text-xl font-semibold text-slate-900">{run?.flow_key ?? run?.id}</h1>
                    {run ? <RunStatusBadge status={run.status} /> : null}
                    <span className="text-sm text-slate-500">{formatDuration(run?.started_at ?? null, run?.finished_at ?? null)}</span>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <Button variant="secondary" size="sm" leadingIcon={<RefreshCw size={13} />} onClick={() => void handleRetry()}>
                      Re-run
                    </Button>
                    {isRunning ? (
                      <Button variant="destructive" size="sm" leadingIcon={<XCircle size={13} />} onClick={() => void handleCancel()}>
                        Cancel
                      </Button>
                    ) : null}
                    {run ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        leadingIcon={<Terminal size={13} />}
                        onClick={() => navigate(`/monitor/${run.id}`)}
                      >
                        Monitor
                      </Button>
                    ) : null}
                  </div>
                </div>

                <div className="border-b border-slate-200">
                  <nav className="flex gap-1" role="tablist">
                    {TABS.map((tab) => (
                      <button
                        key={tab}
                        type="button"
                        role="tab"
                        aria-selected={activeTab === tab}
                        onClick={() => setActiveTab(tab)}
                        className={`border-b-2 px-3 py-2 text-sm ${
                          activeTab === tab
                            ? "border-indigo-600 font-medium text-indigo-600"
                            : "border-transparent text-slate-500 hover:text-slate-700"
                        }`}
                      >
                        {tab}
                      </button>
                    ))}
                  </nav>
                </div>

                {activeTab === "Overview" ? (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-md border border-slate-200 bg-white p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Run ID</p>
                      <div className="mt-1 flex items-center gap-2">
                        <code className="text-xs text-slate-700">{run?.id}</code>
                        <button
                          type="button"
                          className="text-slate-400 hover:text-slate-600"
                          onClick={() => {
                            if (run?.id) void navigator.clipboard.writeText(run.id);
                          }}
                        >
                          <Copy size={12} />
                        </button>
                      </div>
                    </div>

                    <div className="rounded-md border border-slate-200 bg-white p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Prefect Flow Run</p>
                      <div className="mt-1 flex items-center gap-2">
                        <span className="truncate text-xs text-slate-700">{run?.prefect_flow_run_id || "--"}</span>
                        {run?.prefect_flow_run_id ? (
                          <button
                            type="button"
                            className="text-slate-400 hover:text-slate-600"
                            onClick={() => {
                              void navigator.clipboard.writeText(run.prefect_flow_run_id);
                            }}
                          >
                            <Copy size={12} />
                          </button>
                        ) : null}
                        {prefectRunUrl ? (
                          <a
                            href={prefectRunUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-slate-400 hover:text-slate-600"
                            aria-label="Open Prefect run"
                          >
                            <ExternalLink size={12} />
                          </a>
                        ) : null}
                      </div>
                      {run?.prefect_flow_run_id && !prefectRunUrl ? (
                        <p className="mt-2 text-[11px] text-slate-500">
                          Set <code>VITE_PREFECT_UI_BASE_URL</code> to enable deep links into Prefect.
                        </p>
                      ) : null}
                    </div>

                    <div className="rounded-md border border-slate-200 bg-white p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Created</p>
                      <p className="mt-1 text-sm text-slate-700">{formatDateTime(run?.created_at ?? null)}</p>
                    </div>

                    <div className="rounded-md border border-slate-200 bg-white p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Started</p>
                      <p className="mt-1 text-sm text-slate-700">{formatDateTime(run?.started_at ?? null)}</p>
                    </div>

                    <div className="rounded-md border border-slate-200 bg-white p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Finished</p>
                      <p className="mt-1 text-sm text-slate-700">{formatDateTime(run?.finished_at ?? null)}</p>
                    </div>

                    <div className="rounded-md border border-slate-200 bg-white p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-400">Duration</p>
                      <p className="mt-1 text-sm text-slate-700">{formatDuration(run?.started_at ?? null, run?.finished_at ?? null)}</p>
                    </div>

                    {workflowValidation ? (
                      <div className="col-span-2 rounded-md border border-slate-200 bg-white p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <p className="text-xs uppercase tracking-wide text-slate-400">Source Workflow Validation</p>
                            <p className="mt-1 text-sm font-medium text-slate-700">
                              {sourceWorkflow?.name ?? run?.flow_key}
                            </p>
                          </div>
                          <span
                            className={`rounded px-2 py-1 text-xs font-medium ${
                              workflowValidation.status === "safe"
                                ? "bg-emerald-50 text-emerald-700"
                                : workflowValidation.status === "invalid"
                                ? "bg-red-50 text-red-700"
                                : "bg-amber-50 text-amber-700"
                            }`}
                          >
                            {workflowValidation.status === "safe"
                              ? "Chain Safe"
                              : workflowValidation.status === "invalid"
                              ? "Invalid Chain"
                              : "Advisory Chain"}
                          </span>
                        </div>
                        {workflowValidation.errors.length > 0 ? (
                          <div className="mt-3 space-y-2">
                            {workflowValidation.errors.map((message) => (
                              <p key={message} className="rounded bg-red-50 px-3 py-2 text-xs text-red-700">
                                {message}
                              </p>
                            ))}
                          </div>
                        ) : null}
                        {workflowValidation.warnings.length > 0 ? (
                          <div className="mt-3 space-y-2">
                            {workflowValidation.warnings.map((message) => (
                              <p key={message} className="rounded bg-amber-50 px-3 py-2 text-xs text-amber-700">
                                {message}
                              </p>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}

                {activeTab === "Logs" ? (
                  <div className="overflow-hidden rounded-md border border-slate-800 bg-slate-950">
                    <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Live Logs</p>
                      <span className="text-xs text-slate-500">{logsStream.isStreaming ? "Streaming" : "Idle"}</span>
                    </div>
                    <div className="max-h-[520px] space-y-1 overflow-auto p-4 font-mono text-xs">
                      <AsyncState
                        isLoading={logsStream.isStreaming && visibleLogs.length === 0}
                        error={logsStream.error}
                        isEmpty={!logsStream.isStreaming && visibleLogs.length === 0}
                        emptyTitle="No log lines"
                        emptyDescription="Start the run or check stream connectivity."
                        className="flex h-28 items-center justify-center"
                      >
                        {visibleLogs.map((line, idx) => (
                          <div key={`${line.time}-${idx}`} className="flex gap-3">
                            <span className="w-16 text-slate-500">{line.time}</span>
                            <span className="w-12 text-sky-400">{line.level}</span>
                            <span className="text-slate-200">{line.message}</span>
                          </div>
                        ))}
                      </AsyncState>
                    </div>
                  </div>
                ) : null}

                {activeTab === "Artifacts" ? (
                  <AsyncState
                    isLoading={loadingArtifacts}
                    error={artifactsError}
                    isEmpty={!loadingArtifacts && artifacts.length === 0}
                    emptyTitle="No artifacts"
                    emptyDescription="Artifacts will appear after step outputs are persisted."
                    onRetry={() => {
                      void artifactsQuery.refetch();
                    }}
                  >
                    <div className="grid grid-cols-2 gap-4">
                      {artifacts.map((artifact) => (
                        <div key={artifact.id} className="rounded-md border border-slate-200 bg-white p-4">
                          <div className="mb-2 flex items-center justify-between">
                            <p className="text-xs uppercase tracking-wide text-slate-400">{artifact.kind}</p>
                            <span className="text-xs text-slate-400">{formatRelativeTime(artifact.created_at)}</span>
                          </div>
                          <p className="truncate text-sm text-slate-700">{artifact.uri}</p>
                          <div className="mt-3 flex gap-2">
                            <Button
                              variant="secondary"
                              size="xs"
                              leadingIcon={<Download size={12} />}
                              onClick={() => {
                                void handleArtifactOpen(artifact.id);
                              }}
                            >
                              Open
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </AsyncState>
                ) : null}

                {activeTab === "Strategy Report" ? (
                  <AsyncState
                    isLoading={loadingArtifacts}
                    error={artifactsError}
                    isEmpty={false}
                    onRetry={() => {
                      void artifactsQuery.refetch();
                    }}
                  >
                    <div className="space-y-4">
                      <div className="rounded-md border border-slate-200 bg-white p-5">
                        <div className="flex items-start gap-3">
                          <div className="rounded-full bg-indigo-50 p-2 text-indigo-600">
                            <FileText size={18} />
                          </div>
                          <div className="space-y-1">
                            <p className="text-xs uppercase tracking-wide text-slate-400">Strategy Readout</p>
                            <h2 className="text-base font-semibold text-slate-900">{strategyReport.headline}</h2>
                            <p className="text-sm text-slate-600">{strategyReport.summary}</p>
                            {workflowValidation ? (
                              <p className="text-xs text-slate-500">
                                Source workflow status:{" "}
                                {workflowValidation.status === "safe"
                                  ? "Chain Safe"
                                  : workflowValidation.status === "invalid"
                                  ? "Invalid Chain"
                                  : "Advisory Chain"}
                              </p>
                            ) : null}
                          </div>
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="rounded-md border border-slate-200 bg-white p-4">
                          <p className="text-xs uppercase tracking-wide text-slate-400">Execution Signals</p>
                          <div className="mt-3 space-y-2 text-sm text-slate-700">
                            {strategyReport.executionSignals.map((line) => (
                              <p key={line}>{line}</p>
                            ))}
                          </div>
                        </div>

                        <div className="rounded-md border border-slate-200 bg-white p-4">
                          <p className="text-xs uppercase tracking-wide text-slate-400">Next Actions</p>
                          <div className="mt-3 space-y-2 text-sm text-slate-700">
                            {strategyReport.nextActions.map((line) => (
                              <p key={line}>{line}</p>
                            ))}
                          </div>
                        </div>
                      </div>

                      <div className="rounded-md border border-slate-200 bg-white p-4">
                        <p className="text-xs uppercase tracking-wide text-slate-400">Run Inputs</p>
                        <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-700">
                          {strategyReport.parameterHighlights.map((line) => (
                            <div key={line} className="rounded-md bg-slate-50 px-3 py-2">
                              {line}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </AsyncState>
                ) : null}
              </div>
            </AsyncState>
          </div>
        </main>

        <aside className="col-span-3 min-h-0 overflow-auto bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">Related Runs</h3>
            <Button
              variant="ghost"
              size="xs"
              onClick={() => {
                void Promise.all([runQuery.refetch(), runsQuery.refetch()]);
              }}
            >
              Refresh
            </Button>
          </div>

          <AsyncState
            isLoading={loadingRun}
            isEmpty={!loadingRun && relatedRuns.length === 0}
            emptyTitle="No related runs"
            emptyDescription="Trigger additional runs to compare execution history."
            className="py-4"
          >
            <div className="space-y-2">
              {relatedRuns.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => navigate(`/runs/${item.id}`)}
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-left hover:bg-slate-50"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <RunStatusBadge status={item.status} />
                    <span className="text-xs text-slate-400">{formatDuration(item.started_at, item.finished_at)}</span>
                  </div>
                  <p className="truncate text-xs font-medium text-slate-700">{item.flow_key || item.id}</p>
                  <p className="text-[11px] text-slate-400">{formatRelativeTime(item.started_at)}</p>
                </button>
              ))}
            </div>
          </AsyncState>
        </aside>
      </div>
    </AppShell>
  );
}
