import { useQuery } from "@tanstack/react-query";

import { browseAgents, type DiscoveryAgent } from "../api/discovery";

export function useAgentCatalog(workspaceId: string | null) {
  return useQuery<{ results: DiscoveryAgent[]; total: number }>({
    queryKey: ["agent-catalog", workspaceId],
    queryFn: () => browseAgents(workspaceId!),
    enabled: Boolean(workspaceId),
    staleTime: 30_000,
  });
}
