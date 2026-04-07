import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ChevronLeft, Copy, Download, ExternalLink, FileText, RefreshCw, Terminal, XCircle } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { RunStatusBadge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import { cancelRun, getRun, getRuns, retryRun, type Run } from "../api/runs";
import { getArtifactAccess, getArtifacts, type Artifact } from "../api/artifacts";
import { buildRunLogsStreamUrl } from "../api/logs";
import { useEventSource } from "../hooks/useEventSource";
import { formatDuration, formatRelativeTime } from "../utils/time";

const TABS = ["Overview", "Logs", "Artifacts", "Strategy Report"] as const;
type Tab = (typeof TABS)[number];

type LogEvent = {
  level?: string;
  time?: string;
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

export default function RunDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { workspaceId } = useAuth();

  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [run, setRun] = useState<Run | null>(null);
  const [relatedRuns, setRelatedRuns] = useState<Run[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);

  const [loadingRun, setLoadingRun] = useState(true);
  const [runError, setRunError] = useState<string | null>(null);
  const [loadingArtifacts, setLoadingArtifacts] = useState(false);
  const [artifactsError, setArtifactsError] = useState<string | null>(null);

  const loadRun = async () => {
    if (!workspaceId || !id) return;
    setLoadingRun(true);
    setRunError(null);

    try {
      const [current, allRuns] = await Promise.all([getRun(id, workspaceId), getRuns(workspaceId)]);
      setRun(current);
      setRelatedRuns(allRuns.items.filter((item) => item.id !== id).slice(0, 5));
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Failed to load run details");
    } finally {
      setLoadingRun(false);
    }
  };

  const loadArtifacts = async () => {
    if (!workspaceId || !id) return;
    setLoadingArtifacts(true);
    setArtifactsError(null);

    try {
      const res = await getArtifacts({ workspace_id: workspaceId, workflow_run_id: id });
      setArtifacts(res.items ?? []);
    } catch (err: unknown) {
      setArtifactsError(err instanceof Error ? err.message : "Failed to load artifacts");
    } finally {
      setLoadingArtifacts(false);
    }
  };

  useEffect(() => {
    void loadRun();
  }, [id, workspaceId]);

  useEffect(() => {
    if (activeTab !== "Artifacts") return;
    void loadArtifacts();
  }, [activeTab, id, workspaceId]);

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
      time: event.time ?? formatLogTime(event.timestamp),
      message: event.msg ?? event.message ?? "",
    }))
    .filter((event) => event.message && event.message !== "__STREAM_END__");

  const isRunning = run?.status === "running";

  const handleCancel = async () => {
    if (!id || !workspaceId) return;
    try {
      await cancelRun(id, workspaceId);
      await loadRun();
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Failed to cancel run");
    }
  };

  const handleRetry = async () => {
    if (!id || !workspaceId) return;
    try {
      await retryRun(id, workspaceId);
      navigate("/runs");
    } catch (err: unknown) {
      setRunError(err instanceof Error ? err.message : "Failed to retry run");
    }
  };

  const handleArtifactOpen = async (artifactId: string) => {
    if (!workspaceId) return;
    try {
      const access = await getArtifactAccess(artifactId, workspaceId);
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
                void loadRun();
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
                          <a href="#" className="text-slate-400 hover:text-slate-600" aria-label="Open Prefect run">
                            <ExternalLink size={12} />
                          </a>
                        ) : null}
                      </div>
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
                      void loadArtifacts();
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
                  <div className="rounded-md border border-slate-200 bg-white p-8 text-center">
                    <FileText size={28} className="mx-auto mb-3 text-slate-300" />
                    <p className="text-sm font-medium text-slate-700">Strategy report status follows run outputs.</p>
                    <p className="mt-1 text-xs text-slate-500">Use Artifacts tab or Reports page for generated narratives.</p>
                  </div>
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
                void loadRun();
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
