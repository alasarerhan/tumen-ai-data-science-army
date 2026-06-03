import { apiGet, apiPost, qs } from "./client";

const PREFECT_UI_BASE_URL = ((import.meta.env.VITE_PREFECT_UI_BASE_URL as string | undefined) || "").replace(/\/+$/, "");

export type RunStatus = "running" | "success" | "failed" | "pending" | "cancelled";

export interface Run {
  id: string;
  workspace_id: string;
  tenant_id: string;
  flow_key: string;
  workflow_spec_id: string | null;
  workflow_version: number | null;
  trigger_type: string | null;
  input_artifact_ids: string[];
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
  workflow_spec_id?: string;
  workflow_version?: number;
  trigger_type?: string;
  input_artifact_ids?: string[];
}) => apiPost<Run>("/v1/runs", body);

export interface WorkflowNodeExecution {
  id: string;
  tenant_id: string;
  workspace_id: string;
  workflow_run_id: string;
  node_id: string;
  node_type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "skipped" | "retrying" | "waiting_approval" | string;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  logs: unknown[];
  error: string | null;
  retry_count: number;
  produced_artifact_ids: string[];
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const getRunNodes = (run_id: string, workspace_id: string) =>
  apiGet<{ items: WorkflowNodeExecution[] }>(`/v1/runs/${run_id}/nodes${qs({ workspace_id })}`);

export const retryRunNode = (run_id: string, node_id: string, workspace_id: string) =>
  apiPost<WorkflowNodeExecution>(`/v1/runs/${run_id}/nodes/${node_id}/retry`, { workspace_id });

export const resumeRun = (run_id: string, workspace_id: string) =>
  apiPost<{ resumed_nodes: WorkflowNodeExecution[] }>(`/v1/runs/${run_id}/resume`, { workspace_id });

export const cancelRun = (run_id: string, workspace_id: string) =>
  apiPost<Run>(`/v1/runs/${run_id}/cancel`, { workspace_id });

export const retryRun = (run_id: string, workspace_id: string) =>
  apiPost<Run>(`/v1/runs/${run_id}/retry`, { workspace_id });

export function buildPrefectRunUrl(prefectFlowRunId: string | null | undefined): string | null {
  if (!prefectFlowRunId || !PREFECT_UI_BASE_URL) {
    return null;
  }
  return `${PREFECT_UI_BASE_URL}/flow-runs/flow-run/${encodeURIComponent(prefectFlowRunId)}`;
}

