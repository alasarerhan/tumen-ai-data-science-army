// BUSINESS SCIENCE UNIVERSITY / AI DATA SCIENCE TEAM
// M25 — useRuns React Query hooks
import { useQueries, useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getRuns,
  getRun,
  getRunAgentTraces,
  getRunNodes,
  triggerRun,
  cancelRun,
  retryRun,
  type AgentExecutionTrace,
  type Run,
  type WorkflowNodeExecution,
} from "../api/runs";

export function useRuns(workspace_id: string | null) {
  return useQuery<{ items: Run[] }>({
    queryKey: ["runs", workspace_id],
    queryFn: () => getRuns(workspace_id!),
    enabled: !!workspace_id,
    refetchInterval: 5_000,
  });
}

export function useRun(run_id: string | undefined, workspace_id: string | null) {
  return useQuery<Run>({
    queryKey: ["run", run_id],
    queryFn: () => getRun(run_id!, workspace_id!),
    enabled: !!run_id && !!workspace_id,
    refetchInterval: 3_000,
  });
}

export function useRunAgentTraces(run_id: string | undefined, workspace_id: string | null, enabled = true) {
  return useQuery<{ items: AgentExecutionTrace[] }>({
    queryKey: ["run-agent-traces", run_id, workspace_id],
    queryFn: () => getRunAgentTraces(run_id!, workspace_id!),
    enabled: enabled && !!run_id && !!workspace_id,
    refetchInterval: 5_000,
  });
}

export function useRunNodesForRuns(run_ids: string[], workspace_id: string | null) {
  return useQueries({
    queries: run_ids.map((run_id) => ({
      queryKey: ["run-nodes", run_id, workspace_id],
      queryFn: () => getRunNodes(run_id, workspace_id!),
      enabled: !!workspace_id && !!run_id,
      refetchInterval: 5_000,
    })),
  });
}

export function useTriggerRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: { workspace_id: string; flow_key?: string; parameters?: Record<string, unknown> }) =>
      triggerRun(req),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["runs", variables.workspace_id] });
    },
  });
}

export function useCancelRun(workspace_id: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (run_id: string) => cancelRun(run_id, workspace_id!),
    onSuccess: (_data, run_id) => {
      qc.invalidateQueries({ queryKey: ["run", run_id] });
      qc.invalidateQueries({ queryKey: ["runs", workspace_id] });
    },
  });
}

export function useRetryRun(workspace_id: string | null) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (run_id: string) => retryRun(run_id, workspace_id!),
    onSuccess: (_data, run_id) => {
      qc.invalidateQueries({ queryKey: ["run", run_id] });
      qc.invalidateQueries({ queryKey: ["runs", workspace_id] });
    },
  });
}

