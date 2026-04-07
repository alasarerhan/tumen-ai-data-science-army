import { apiGet, apiPost, qs } from "./client";

export interface Artifact {
  id: string;
  workspace_id: string;
  tenant_id: string;
  workflow_run_id: string | null;
  kind: string;
  uri: string;
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
}) => apiGet<{ items: Artifact[] }>(`/v1/artifacts${qs(params)}`);

export const registerArtifact = (body: {
  workspace_id: string;
  workflow_run_id?: string;
  kind: string;
  uri: string;
}) => apiPost<Artifact>("/v1/artifacts", body);

export const getArtifactAccess = (artifact_id: string, workspace_id: string) =>
  apiGet<ArtifactAccess>(`/v1/artifacts/${artifact_id}/access${qs({ workspace_id })}`);
