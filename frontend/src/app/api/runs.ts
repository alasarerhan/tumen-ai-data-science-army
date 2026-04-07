import { apiGet, apiPost, qs } from "./client";

export type RunStatus = "running" | "success" | "failed" | "pending" | "cancelled";

export interface Run {
  id: string;
  workspace_id: string;
  tenant_id: string;
  flow_key: string;
  prefect_flow_run_id: string;
  status: RunStatus | string;
  parameters: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export const getRuns = (workspace_id: string) =>
  apiGet<{ items: Run[] }>(`/v1/runs${qs({ workspace_id })}`);

export const getRun = (run_id: string, workspace_id: string) =>
  apiGet<Run>(`/v1/runs/${run_id}${qs({ workspace_id })}`);

export const triggerRun = (body: {
  workspace_id: string;
  flow_key?: string;
  parameters?: Record<string, unknown>;
}) => apiPost<Run>("/v1/runs", body);

export const cancelRun = (run_id: string, workspace_id: string) =>
  apiPost<Run>(`/v1/runs/${run_id}/cancel`, { workspace_id });

export const retryRun = (run_id: string, workspace_id: string) =>
  apiPost<Run>(`/v1/runs/${run_id}/retry`, { workspace_id });

