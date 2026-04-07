import { apiDelete, apiGet, apiPost, apiPut, qs } from "./client";

export interface DataSource {
  id: string;
  workspace_id: string;
  tenant_id: string;
  name: string;
  kind: string;
  connection_uri: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
}

export const getDataSources = (workspace_id: string) =>
  apiGet<{ items: DataSource[] }>(`/v1/data-sources${qs({ workspace_id })}`);

export const createDataSource = (body: {
  workspace_id: string;
  name: string;
  kind: string;
  connection_uri: string;
  metadata?: Record<string, unknown>;
}) => apiPost<DataSource>("/v1/data-sources", body);

export const updateDataSource = (
  id: string,
  body: {
    workspace_id: string;
    name?: string;
    kind?: string;
    connection_uri?: string;
    metadata?: Record<string, unknown>;
  },
) => apiPut<DataSource>(`/v1/data-sources/${id}`, body);

export const deleteDataSource = (id: string, workspace_id: string) =>
  apiDelete(`/v1/data-sources/${id}${qs({ workspace_id })}`);

export const testDataSource = (id: string, workspace_id: string) =>
  apiPost<{ status: string; message: string }>(`/v1/data-sources/${id}/test`, { workspace_id });

