import { useQuery } from "@tanstack/react-query";

import { queryControlPlane, type PlatformQueryResultArtifact } from "../api/controlPlane";
import { browseAgents, type DiscoveryAgent } from "../api/discovery";

export function useAgentCatalog(workspaceId: string | null) {
  return useQuery<{ results: DiscoveryAgent[]; total: number }>({
    queryKey: ["agent-catalog", workspaceId],
    queryFn: () => browseAgents(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  });
}

export function useAgentExecutionSummary(workspaceId: string | null) {
  return useQuery<PlatformQueryResultArtifact>({
    queryKey: ["agent-execution-summary", workspaceId],
    queryFn: () =>
      queryControlPlane({
        workspace_id: workspaceId!,
        query: "agent execution traces and node executions",
        resource_keys: ["run.nodes", "agent.traces"],
        limit: 100,
      }),
    enabled: Boolean(workspaceId),
    staleTime: 15_000,
  });
}
