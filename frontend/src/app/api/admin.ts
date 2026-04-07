import { apiGet, apiPost, qs } from "./client";

export interface DlqEvent {
  id: string;
  original_event_id: string;
  aggregate_type: string;
  aggregate_id: string;
  event_type: string;
  payload_json: string | null;
  final_error: string | null;
  retry_count: number;
  original_created_at: string;
  moved_to_dlq_at: string;
  reviewed: boolean;
  reviewed_at: string | null;
  resolution_note: string | null;
}

export interface QueueStats {
  pending: number;
  processing: number;
  failed: number;
  dlq: number;
}

export interface SchedulerStatus {
  is_leader: boolean;
  leader_id: string | null;
  jobs: Array<{
    job_name: string;
    job_type: string;
    enabled: boolean;
    last_run_at: string | null;
    next_run_at: string | null;
    last_run_status: string | null;
  }>;
}

export interface MemoryStats {
  rss_bytes: number;
  vms_bytes: number;
  percent: number;
  available_system_memory: number;
  total_system_memory: number;
  growth_rate_bytes_per_minute: number;
  recommendations: string[];
}

export interface FinOpsSummary {
  storage: {
    artifacts: number;
    uploads: number;
    expired_artifacts: number;
  };
  compute: {
    workflow_runs: number;
  };
  cache: {
    backend: string;
    entries: number;
  };
  config: {
    artifact_retention_days: number;
    upload_max_mb: number;
    agent_cache_enabled: boolean;
  };
  recommendations: string[];
}

export const getDlqEvents = (params?: { unreviewed_only?: boolean }) =>
  apiGet<{ items: DlqEvent[] }>(`/v1/admin/dlq${qs(params ?? {})}`);

export const replayDlqEvent = (event_id: string) =>
  apiPost<{ status: string; new_event_id: string }>(`/v1/admin/dlq/${event_id}/replay`, {});

export const getQueueStats = () =>
  apiGet<QueueStats>("/v1/admin/queue-stats");

export const getSchedulerStatus = () =>
  apiGet<SchedulerStatus>("/v1/admin/scheduler");

export const getMemoryStats = () =>
  apiGet<MemoryStats>("/v1/admin/memory");

export const getFinOpsSummary = () =>
  apiGet<FinOpsSummary>("/v1/finops/summary");

export const runArtifactCleanup = (dry_run: boolean = true) =>
  apiPost<{ dry_run: boolean; artifacts_deleted: number; files_deleted: number; bytes_freed: number; errors: string[] }>(
    `/v1/finops/artifacts/cleanup${qs({ dry_run })}`,
    {},
  );
