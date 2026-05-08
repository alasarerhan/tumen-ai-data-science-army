import { useMutation, useQuery } from "@tanstack/react-query";
import { getArtifactAccess, getArtifacts, type Artifact, type ArtifactAccess } from "../api/artifacts";

export function useRunArtifacts(runId: string | undefined, workspaceId: string | null, enabled = true) {
  return useQuery<{ items: Artifact[] }>({
    queryKey: ["run-artifacts", workspaceId, runId],
    queryFn: () => getArtifacts({ workspace_id: workspaceId!, workflow_run_id: runId }),
    enabled: Boolean(enabled && runId && workspaceId),
  });
}

export function useArtifactAccess(workspaceId: string | null) {
  return useMutation<ArtifactAccess, Error, string>({
    mutationFn: (artifactId: string) => getArtifactAccess(artifactId, workspaceId!),
  });
}
