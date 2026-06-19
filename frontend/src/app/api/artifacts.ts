import { apiGet, qs } from "./client";

export interface Artifact {
  id: string;
  workspace_id: string;
  tenant_id: string;
  workflow_run_id: string | null;
  kind: string;
  uri: string;
  artifact_type?: string;
  storage_uri?: string;
  produced_by_node_id: string | null;
  parent_artifact_ids: string[];
  created_at: string | null;
}

export interface ArtifactAccess {
  artifact_id: string;
  kind: string;
  access_mode: string;
  delivery: {
    type: "redirect" | "s3" | "gcs" | "azure-blob" | "internal-stream";
    url: string;
  };
}

export const getArtifacts = (params: {
  workspace_id: string;
  workflow_run_id?: string;
  kind?: string;
  cursor?: string;
  limit?: number;
}) => apiGet<{ items: Artifact[] }>(`/v1/artifacts${qs(params)}`);

export const getArtifactAccess = (artifact_id: string, workspace_id: string) =>
  apiGet<ArtifactAccess>(`/v1/artifacts/${artifact_id}/access${qs({ workspace_id })}`);
