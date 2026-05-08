import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDataSource,
  deleteDataSource,
  getDataSources,
  testDataSource,
  type DataSource,
} from "../api/datasources";

export function useDataSources(workspaceId: string | null) {
  return useQuery<{ items: DataSource[] }>({
    queryKey: ["data-sources", workspaceId],
    queryFn: () => getDataSources(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useCreateDataSource(workspaceId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createDataSource,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-sources", workspaceId] });
    },
  });
}

export function useDeleteDataSource(workspaceId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dataSourceId: string) => deleteDataSource(dataSourceId, workspaceId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-sources", workspaceId] });
    },
  });
}

export function useTestDataSource(workspaceId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dataSourceId: string) => testDataSource(dataSourceId, workspaceId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["data-sources", workspaceId] });
    },
  });
}
