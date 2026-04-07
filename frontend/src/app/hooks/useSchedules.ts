import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  listScheduledDeployments,
  getWorkflowSchedule,
  pauseScheduledDeployment,
  resumeScheduledDeployment,
  type ScheduledDeployment,
} from "../api/scheduler";

export function useSchedules(workspace_id: string | null) {
  return useQuery<{ items: ScheduledDeployment[] }>({
    queryKey: ["schedules", workspace_id],
    queryFn: () => listScheduledDeployments(workspace_id!),
    enabled: !!workspace_id,
    refetchInterval: 30_000,
  });
}

export function useWorkflowSchedule(workflow_id: string | undefined, workspace_id: string | null) {
  return useQuery<ScheduledDeployment>({
    queryKey: ["schedule", workflow_id],
    queryFn: () => getWorkflowSchedule(workflow_id!, workspace_id!),
    enabled: !!workflow_id && !!workspace_id,
  });
}

export function usePauseSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deployment_id, workspace_id }: { deployment_id: string; workspace_id: string }) =>
      pauseScheduledDeployment(deployment_id, workspace_id),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["schedules", variables.workspace_id] });
    },
  });
}

export function useResumeSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ deployment_id, workspace_id }: { deployment_id: string; workspace_id: string }) =>
      resumeScheduledDeployment(deployment_id, workspace_id),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["schedules", variables.workspace_id] });
    },
  });
}
