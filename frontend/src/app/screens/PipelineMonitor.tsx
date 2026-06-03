import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { Send, Radio, RefreshCw, WifiOff, Wifi } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import { getRuns, type Run } from "../api/runs";
import { getWorkflows, type WorkflowSpec } from "../api/workflows";
import { buildRunLogsStreamUrl } from "../api/logs";
import {
  buildSignalStreamUrl,
  emitSignal,
  listSignals,
  type SignalDto,
  type SignalStreamEvent,
} from "../api/signals";
import { useEventSource } from "../hooks/useEventSource";
import { useToast } from "../hooks/useToast";
import {
  getWorkflowValidationLabel,
  getWorkflowValidationVariant,
  resolveWorkflowValidationForFlowKey,
} from "../utils/workflowValidation";

const SIGNAL_TYPES: Array<SignalDto["signal_type"]> = ["pause", "resume", "skip", "modify", "annotate", "cancel"];

type LogEvent = {
  ts?: string;
  level?: string;
  msg?: string;
  time?: string;
  message?: string;
};

function formatTime(value: string | null | undefined): string {
  if (!value) return "--";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString();
}

export default function PipelineMonitor() {
  const navigate = useNavigate();
  const { runId: routeRunId } = useParams();
  const { workspaceId } = useAuth();
  const toast = useToast();

  const [runs, setRuns] = useState<Run[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowSpec[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(routeRunId ?? null);

  const [signalType, setSignalType] = useState<SignalDto["signal_type"]>("annotate");
  const [targetStep, setTargetStep] = useState("");
  const [note, setNote] = useState("");
  const [submittingSignal, setSubmittingSignal] = useState(false);
  const [signalHistory, setSignalHistory] = useState<SignalDto[]>([]);

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? null;
  const selectedRunWorkflowValidation = useMemo(
    () => resolveWorkflowValidationForFlowKey(workflows, selectedRun?.flow_key),
    [workflows, selectedRun?.flow_key],
  );

  const logsUrl = useMemo(() => {
    if (!workspaceId || !selectedRunId) return null;
    return buildRunLogsStreamUrl(selectedRunId, workspaceId);
  }, [workspaceId, selectedRunId]);

  const [signalLastEventId, setSignalLastEventId] = useState<string | null>(null);

  const signalsUrl = useMemo(() => {
    if (!workspaceId || !selectedRunId) return null;
    return buildSignalStreamUrl(selectedRunId, workspaceId, signalLastEventId ?? undefined);
  }, [workspaceId, selectedRunId, signalLastEventId]);

  const logsStream = useEventSource<LogEvent>({
    url: logsUrl,
    enabled: Boolean(logsUrl),
    autoReconnect: true,
    maxRetries: 5,
    retryDelayMs: 1000,
  });

  const signalsStream = useEventSource<SignalStreamEvent>({
    url: signalsUrl,
    enabled: Boolean(signalsUrl),
    eventIdField: "id",
    autoReconnect: true,
    maxRetries: 5,
    retryDelayMs: 1000,
  });

  useEffect(() => {
    if (!workspaceId) return;
    setLoadingRuns(true);
    setRunsError(null);
    getRuns(workspaceId)
      .then((res) => {
        setRuns(res.items);
        setSelectedRunId((current) => current ?? res.items[0]?.id ?? null);
      })
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to load runs";
        setRunsError(message);
        toast.error("Run list failed", message);
      })
      .finally(() => setLoadingRuns(false));
    getWorkflows({ workspace_id: workspaceId })
      .then((res) => setWorkflows(res.items))
      .catch((err: unknown) => {
        console.error("Failed to load workflows:", err);
        setWorkflows([]);
      });
  }, [workspaceId]);

  useEffect(() => {
    if (!workspaceId || !selectedRunId) {
      setSignalHistory([]);
      return;
    }
    void listSignals(selectedRunId, workspaceId)
      .then((res) => setSignalHistory(res.items))
      .catch((err: unknown) => {
        console.error("Failed to load signal history:", err);
        setSignalHistory([]);
      });
  }, [selectedRunId, workspaceId]);

  useEffect(() => {
    logsStream.clear();
    signalsStream.clear();
    setSignalLastEventId(null);
  }, [selectedRunId]);

  useEffect(() => {
    for (const event of signalsStream.events) {
      if (event.type !== "message") continue;
      const signal = event.message;
      if (event.id) {
        setSignalLastEventId(event.id);
      }
      setSignalHistory((prev) => {
        if (prev.some((item) => item.id === signal.id)) return prev;
        return [...prev, signal];
      });
    }
  }, [signalsStream.events]);

  const handleEmitSignal = async () => {
    if (!workspaceId || !selectedRunId || submittingSignal) return;
    setSubmittingSignal(true);
    try {
      const created = await emitSignal(selectedRunId, {
        workspace_id: workspaceId,
        signal_type: signalType,
        target_step: targetStep.trim() || undefined,
        note: note.trim() || undefined,
      });
      setSignalHistory((prev) => [...prev, created]);
      setNote("");
      setTargetStep("");
      toast.success("Signal sent", `Signal ${created.signal_type} was emitted successfully.`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to emit signal";
      toast.error("Signal failed", message);
    } finally {
      setSubmittingSignal(false);
    }
  };

  const logLines = logsStream.events
    .map((event) => ({
      time: event.time ?? formatTime(event.ts),
      level: event.level ?? "INFO",
      msg: event.msg ?? event.message ?? "",
    }))
    .filter((event) => event.msg !== "__STREAM_END__");

  const connectionStatus = useMemo(() => {
    if (logsStream.error || signalsStream.error) {
      return {
        status: "error",
        label: "Disconnected",
        icon: <WifiOff size={12} className="text-red-500" />,
        color: "bg-red-50 text-red-700",
      };
    }
    if (logsStream.isStreaming || signalsStream.isStreaming) {
      return {
        status: "connected",
        label: "Live",
        icon: <Radio size={12} className="animate-pulse text-emerald-500" />,
        color: "bg-emerald-50 text-emerald-700",
      };
    }
    return {
      status: "idle",
      label: "Idle",
      icon: <Wifi size={12} className="text-slate-400" />,
      color: "bg-slate-50 text-slate-500",
    };
  }, [logsStream.isStreaming, signalsStream.isStreaming, logsStream.error, signalsStream.error]);

  return (
    <AppShell>
      <div className="grid h-full grid-cols-12">
        <aside className="col-span-3 border-r border-slate-200 bg-white p-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">Pipeline Monitor</h2>
            <Button
              variant="ghost"
              size="xs"
              leadingIcon={<RefreshCw size={12} />}
              onClick={() => {
                if (!workspaceId) return;
                setLoadingRuns(true);
                void getRuns(workspaceId)
                  .then((res) => setRuns(res.items))
                  .finally(() => setLoadingRuns(false));
                void getWorkflows({ workspace_id: workspaceId })
                  .then((res) => setWorkflows(res.items))
                  .catch((err: unknown) => {
                    console.error("Failed to refresh workflows:", err);
                    setWorkflows([]);
                  });
              }}
            >
              Refresh
            </Button>
          </div>

          <AsyncState
            isLoading={loadingRuns}
            error={runsError}
            isEmpty={!loadingRuns && runs.length === 0}
            emptyTitle="No runs found"
            emptyDescription="Trigger a workflow run to monitor it."
            className="py-5"
          >
            <div className="space-y-1">
              {runs.map((run) => {
                const workflowValidation = resolveWorkflowValidationForFlowKey(workflows, run.flow_key);
                return (
                <button
                  key={run.id}
                  type="button"
                  onClick={() => {
                    setSelectedRunId(run.id);
                    navigate(`/monitor/${run.id}`);
                  }}
                  className={`w-full rounded-md border px-3 py-2 text-left ${
                    selectedRunId === run.id
                      ? "border-indigo-300 bg-indigo-50"
                      : "border-transparent hover:border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-sm font-medium text-slate-700">{run.flow_key}</p>
                    {workflowValidation ? (
                      <Badge variant={getWorkflowValidationVariant(workflowValidation.status)} size="sm">
                        {getWorkflowValidationLabel(workflowValidation.status)}
                      </Badge>
                    ) : null}
                  </div>
                  <p className="truncate text-xs text-slate-400">{run.id}</p>
                </button>
                );
              })}
            </div>
          </AsyncState>
        </aside>

        <main className="col-span-9 grid grid-cols-12 gap-0">
          <section className="col-span-7 border-r border-slate-200">
            <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-800">Run Timeline & Live Logs</h3>
                <p className="text-xs text-slate-400">{selectedRun?.id ?? "Select a run"}</p>
              </div>
              <div className="flex items-center gap-3">
                {selectedRunWorkflowValidation ? (
                  <Badge variant={getWorkflowValidationVariant(selectedRunWorkflowValidation.status)} size="sm">
                    {getWorkflowValidationLabel(selectedRunWorkflowValidation.status)}
                  </Badge>
                ) : null}
                <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs ${connectionStatus.color}`}>
                  {connectionStatus.icon}
                  {connectionStatus.label}
                </span>
                {(logsStream.reconnectAttempts > 0 || signalsStream.reconnectAttempts > 0) && (
                  <span className="text-xs text-amber-600">
                    Reconnecting... ({Math.max(logsStream.reconnectAttempts, signalsStream.reconnectAttempts)})
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-3 p-4">
              <div className="rounded-md border border-slate-200 bg-white p-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Timeline</p>
                <ul className="space-y-2 text-xs">
                  <li className="flex items-center justify-between rounded bg-slate-50 px-2 py-1">
                    <span>Created</span>
                    <span>{formatTime(selectedRun?.created_at)}</span>
                  </li>
                  <li className="flex items-center justify-between rounded bg-slate-50 px-2 py-1">
                    <span>Started</span>
                    <span>{formatTime(selectedRun?.started_at)}</span>
                  </li>
                  <li className="flex items-center justify-between rounded bg-slate-50 px-2 py-1">
                    <span>Status</span>
                    <span className="uppercase">{selectedRun?.status ?? "--"}</span>
                  </li>
                </ul>
              </div>

              <div className="h-[420px] overflow-auto rounded-md border border-slate-800 bg-slate-950 p-3 font-mono text-xs">
                {logLines.length === 0 ? (
                  <p className="text-slate-500">No log entries yet.</p>
                ) : (
                  <div className="space-y-1">
                    {logLines.map((line, idx) => (
                      <div key={`${line.time}-${idx}`} className="flex gap-3">
                        <span className="w-16 text-slate-500">{line.time}</span>
                        <span className="w-12 text-sky-400">{line.level}</span>
                        <span className="text-slate-200">{line.msg}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className="col-span-5 bg-white">
            <div className="border-b border-slate-200 px-4 py-3">
              <h3 className="text-sm font-semibold text-slate-800">Signal History & Controls</h3>
              <p className="text-xs text-slate-400">Emit optional intervention signals without stopping the pipeline.</p>
            </div>

            <div className="space-y-4 p-4">
              <div className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Send Signal</p>
                <select
                  value={signalType}
                  onChange={(event) => setSignalType(event.target.value as SignalDto["signal_type"])}
                  className="h-8 w-full rounded border border-slate-300 px-2 text-sm"
                >
                  {SIGNAL_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
                <input
                  value={targetStep}
                  onChange={(event) => setTargetStep(event.target.value)}
                  placeholder="Target step (optional)"
                  className="h-8 w-full rounded border border-slate-300 px-2 text-sm"
                />
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  placeholder="Note or payload summary"
                  className="min-h-20 w-full resize-none rounded border border-slate-300 px-2 py-1 text-sm"
                />
                <Button
                  variant="primary"
                  size="sm"
                  fullWidth
                  leadingIcon={<Send size={13} />}
                  disabled={!selectedRunId || submittingSignal}
                  onClick={() => {
                    void handleEmitSignal();
                  }}
                >
                  {submittingSignal ? "Sending..." : "Emit Signal"}
                </Button>
              </div>

              <div className="max-h-[380px] space-y-2 overflow-auto rounded-md border border-slate-200 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Signal History</p>
                {signalHistory.length === 0 ? (
                  <p className="text-xs text-slate-400">No signals yet.</p>
                ) : (
                  signalHistory.map((signal) => (
                    <div key={signal.id} className="rounded border border-slate-200 bg-slate-50 px-2 py-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold uppercase text-slate-700">{signal.signal_type}</span>
                        <span className="text-slate-400">{formatTime(signal.created_at)}</span>
                      </div>
                      <p className="mt-1 text-slate-600">{signal.note || "No note"}</p>
                      {signal.target_step ? (
                        <p className="mt-1 text-[11px] text-slate-500">Target: {signal.target_step}</p>
                      ) : null}
                    </div>
                  ))
                )}
              </div>

              {signalsStream.error ? (
                <div className="rounded border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
                  Signal stream error: {signalsStream.error}
                  <Button
                    variant="ghost"
                    size="xs"
                    className="ml-2"
                    onClick={() => signalsStream.reconnect()}
                  >
                    Reconnect
                  </Button>
                </div>
              ) : null}
            </div>
          </section>
        </main>
      </div>
    </AppShell>
  );
}
