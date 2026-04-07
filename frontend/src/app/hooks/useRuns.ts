// BUSINESS SCIENCE UNIVERSITY / AI DATA SCIENCE TEAM
// M25 — useRuns React Query hooks
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getRuns, getRun, triggerRun, cancelRun, retryRun, type Run } from "../api/runs";

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

