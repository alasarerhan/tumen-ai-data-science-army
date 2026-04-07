import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getWorkflows, getWorkflow, createWorkflow, publishWorkflow, archiveWorkflow, type WorkflowSpec } from "../api/workflows";

export function useWorkflows(workspace_id: string | null) {
  return useQuery<{ items: WorkflowSpec[] }>({
    queryKey: ["workflows", workspace_id],
    queryFn: () => getWorkflows({ workspace_id: workspace_id! }),
    enabled: !!workspace_id,
    refetchInterval: 30_000,
  });
}

export function useWorkflow(workflow_id: string | undefined, workspace_id: string | null) {
  return useQuery<WorkflowSpec>({
    queryKey: ["workflow", workflow_id],
    queryFn: () => getWorkflow(workflow_id!, workspace_id!),
    enabled: !!workflow_id && !!workspace_id,
  });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { workspace_id: string; name: string; spec: Record<string, unknown>; publish?: boolean }) =>
      createWorkflow(body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["workflows", variables.workspace_id] });
    },
  });
}

export function usePublishWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, workspace_id }: { id: string; workspace_id: string }) =>
      publishWorkflow(id, workspace_id),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["workflow", variables.id] });
      qc.invalidateQueries({ queryKey: ["workflows", variables.workspace_id] });
    },
  });
}

export function useArchiveWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, workspace_id }: { id: string; workspace_id: string }) =>
      archiveWorkflow(id, workspace_id),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["workflow", variables.id] });
      qc.invalidateQueries({ queryKey: ["workflows", variables.workspace_id] });
    },
  });
}
