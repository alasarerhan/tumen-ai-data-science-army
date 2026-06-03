import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router";
import { RefreshCw, Settings, Activity, Trash2 } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { QueueMetricsCard } from "../components/admin/QueueMetricsCard";
import { DlqTable } from "../components/admin/DlqTable";
import { SchedulerStatusCard } from "../components/admin/SchedulerStatusCard";
import { MemoryMetricsCard } from "../components/admin/MemoryMetricsCard";
import {
  getDlqEvents,
  getQueueStats,
  getSchedulerStatus,
  getMemoryStats,
  replayDlqEvent,
  runArtifactCleanup,
  type DlqEvent,
  type QueueStats,
  type SchedulerStatus,
  type MemoryStats,
} from "../api/admin";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
  const [dlqEvents, setDlqEvents] = useState<DlqEvent[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);

  const [loadingDlq, setLoadingDlq] = useState(false);
  const [loadingScheduler, setLoadingScheduler] = useState(false);
  const [loadingMemory, setLoadingMemory] = useState(false);
  const [runningCleanup, setRunningCleanup] = useState(false);

  const [dlqError, setDlqError] = useState<string | null>(null);
  const [schedulerError, setSchedulerError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const fetchQueueStats = useCallback(async () => {
    try {
      const stats = await getQueueStats();
      setQueueStats(stats);
    } catch (err: unknown) {
      console.warn("[AdminDashboard] Failed to fetch queue stats", err);
    }
  }, []);

  const fetchDlqEvents = useCallback(async () => {
    setLoadingDlq(true);
    setDlqError(null);
    try {
      const result = await getDlqEvents({ unreviewed_only: true });
      setDlqEvents(result.items);
    } catch (err: unknown) {
      setDlqError(err instanceof Error ? err.message : "Failed to fetch DLQ events");
    } finally {
      setLoadingDlq(false);
    }
  }, []);

  const fetchSchedulerStatus = useCallback(async () => {
    setLoadingScheduler(true);
    setSchedulerError(null);
    try {
      const status = await getSchedulerStatus();
      setSchedulerStatus(status);
    } catch (err: unknown) {
      setSchedulerStatus(null);
      setSchedulerError(err instanceof Error ? err.message : "Failed to fetch scheduler status");
    } finally {
      setLoadingScheduler(false);
    }
  }, []);

  const fetchMemoryStats = useCallback(async () => {
    setLoadingMemory(true);
    try {
      const stats = await getMemoryStats();
      setMemoryStats(stats);
    } catch {
      setMemoryStats(null);
    } finally {
      setLoadingMemory(false);
    }
  }, []);

  const handleReplayDlqEvent = async (eventId: string) => {
    await replayDlqEvent(eventId);
  };

  const handleCleanupPreview = async () => {
    setRunningCleanup(true);
    setActionNotice(null);
    try {
      const result = await runArtifactCleanup(true);
      setActionNotice(
        result.artifacts_deleted > 0 || result.files_deleted > 0
          ? `Cleanup preview: ${result.artifacts_deleted} artifact records and ${result.files_deleted} files are eligible for deletion.`
          : "Cleanup preview: no expired artifacts are currently eligible for deletion.",
      );
    } catch (err: unknown) {
      setActionNotice(err instanceof Error ? err.message : "Failed to preview artifact cleanup");
    } finally {
      setRunningCleanup(false);
    }
  };

  const refreshAll = () => {
    fetchQueueStats();
    fetchDlqEvents();
    fetchSchedulerStatus();
    fetchMemoryStats();
  };

  useEffect(() => {
    refreshAll();
    const interval = setInterval(refreshAll, 30000);
    return () => clearInterval(interval);
  }, []);

  const overallHealth = (() => {
    if (!queueStats) return "unknown";
    if (queueStats.dlq > 10 || (memoryStats && memoryStats.percent > 80)) return "critical";
    if (queueStats.dlq > 0 || queueStats.failed > 5) return "warning";
    return "healthy";
  })();

  return (
    <AppShell>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">System Health Dashboard</h1>
            <p className="text-sm text-slate-500 mt-1">
              Monitor queue depth, DLQ events, scheduler status, and memory usage.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={<RefreshCw size={14} />}
              onClick={refreshAll}
            >
              Refresh
            </Button>
            <Button
              variant="ghost"
              size="sm"
              leadingIcon={<Settings size={14} />}
              onClick={() => navigate("/settings")}
            >
              Settings
            </Button>
          </div>
        </div>

        {actionNotice ? (
          <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
            {actionNotice}
          </div>
        ) : null}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <QueueMetricsCard
            pending={queueStats?.pending ?? 0}
            processing={queueStats?.processing ?? 0}
            failed={queueStats?.failed ?? 0}
            dlq={queueStats?.dlq ?? 0}
          />
          <SchedulerStatusCard
            status={schedulerStatus}
            loading={loadingScheduler}
          />
          <MemoryMetricsCard
            stats={memoryStats}
            loading={loadingMemory}
          />
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <Button
                variant="secondary"
                size="sm"
                fullWidth
                leadingIcon={<Trash2 size={12} />}
                loading={runningCleanup}
                onClick={() => {
                  void handleCleanupPreview();
                }}
              >
                Preview Cleanup
              </Button>
              <Button
                variant="secondary"
                size="sm"
                fullWidth
                leadingIcon={<Activity size={12} />}
                onClick={() => navigate("/runs")}
              >
                View Metrics
              </Button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <DlqTable
              events={dlqEvents}
              loading={loadingDlq}
              error={dlqError}
              onRefresh={fetchDlqEvents}
              onReplay={handleReplayDlqEvent}
            />
          </div>

          <div className="space-y-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-700 mb-3">System Status</h3>
              <div className="space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Overall Health</span>
                  <span
                    className={
                      overallHealth === "healthy"
                        ? "text-emerald-600"
                        : overallHealth === "warning"
                        ? "text-amber-600"
                        : overallHealth === "critical"
                        ? "text-red-600"
                        : "text-slate-400"
                    }
                  >
                    {overallHealth.charAt(0).toUpperCase() + overallHealth.slice(1)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Scheduler</span>
                  <span
                    className={
                      schedulerStatus?.restricted
                        ? "text-amber-600"
                        : schedulerStatus?.is_leader
                        ? "text-emerald-600"
                        : "text-slate-400"
                    }
                  >
                    {schedulerStatus?.restricted
                      ? "Restricted"
                      : schedulerStatus?.is_leader
                      ? "Active"
                      : "Standby"}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Memory</span>
                  <span className={memoryStats && memoryStats.percent > 80 ? "text-red-600" : "text-slate-600"}>
                    {memoryStats ? `${memoryStats.percent.toFixed(1)}%` : "--"}
                  </span>
                </div>
              </div>
            </div>

            {schedulerError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-700">
                {schedulerError}
              </div>
            ) : schedulerStatus?.restricted && schedulerStatus.message ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
                {schedulerStatus.message}
              </div>
            ) : null}

            {memoryStats?.recommendations && memoryStats.recommendations.length > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
                <h3 className="text-sm font-semibold text-amber-800 mb-2">Recommendations</h3>
                <ul className="space-y-1 text-xs text-amber-700">
                  {memoryStats.recommendations.slice(0, 3).map((rec, idx) => (
                    <li key={idx}>{rec}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
