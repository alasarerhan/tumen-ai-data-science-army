import { apiGet, apiPost, qs } from "./client";

export interface WorkflowSpec {
  id: string;
  workspace_id: string;
  tenant_id: string;
  name: string;
  version: number;
  status: "draft" | "published" | "archived";
  spec: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export const getWorkflows = (params: {
  workspace_id: string;
  name?: string;
  status?: string;
}) => apiGet<{ items: WorkflowSpec[] }>(`/v1/workflows${qs(params)}`);

export const getWorkflow = (id: string, workspace_id: string) =>
  apiGet<WorkflowSpec>(`/v1/workflows/${id}${qs({ workspace_id })}`);

export const createWorkflow = (body: {
  workspace_id: string;
  name: string;
  spec: Record<string, unknown>;
  publish?: boolean;
}) => apiPost<WorkflowSpec>("/v1/workflows", body);

export const publishWorkflow = (id: string, workspace_id: string) =>
  apiPost<{ id: string; name: string; version: number; status: string }>(
    `/v1/workflows/${id}/publish${qs({ workspace_id })}`,
  );

export const archiveWorkflow = (id: string, workspace_id: string) =>
  apiPost<{ id: string; name: string; version: number; status: string }>(
    `/v1/workflows/${id}/archive${qs({ workspace_id })}`,
  );

