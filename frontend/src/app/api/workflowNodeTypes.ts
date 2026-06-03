import { apiGet, qs } from "./client";

export interface WorkflowNodePort {
  name: string;
  artifact_type: string;
  required: boolean;
}

export interface WorkflowNodeType {
  type: string;
  label: string;
  category: string;
  description: string;
  inputs: WorkflowNodePort[];
  outputs: WorkflowNodePort[];
  ui: {
    icon: string;
    color: string;
    config: Array<Record<string, unknown>>;
  };
  timeout_seconds: number;
  retry_policy: {
    max_attempts: number;
    backoff_seconds: number;
  };
  resources: Record<string, unknown>;
}

export const getWorkflowNodeTypes = (workspace_id: string) =>
  apiGet<{ workspace_id: string; items: WorkflowNodeType[] }>(`/v1/workflow-node-types${qs({ workspace_id })}`);
