import { useQuery } from "@tanstack/react-query";
import { getWorkflowChainRules } from "../api/workflowChainRules";

export function useWorkflowChainRules(workspace_id: string | null) {
  return useQuery({
    queryKey: ["workflow-chain-rules", workspace_id],
    queryFn: () => getWorkflowChainRules(workspace_id!),
    enabled: !!workspace_id,
    staleTime: 5 * 60_000,
  });
}
