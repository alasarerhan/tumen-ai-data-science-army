import { apiGet, qs } from "./client";

export interface WorkflowChainRequirement {
  target_variable?: boolean;
  min_incoming_edges?: number;
}

export interface WorkflowChainRule {
  key: string;
  label: string;
  kind: string;
  color: string;
  aliases: string[];
  safe_next: string[];
  conditional_next: string[];
}

export interface WorkflowChainRuleset {
  version: string;
  agents: WorkflowChainRule[];
  requirements: Record<string, WorkflowChainRequirement>;
}

export interface WorkflowAgentCatalogItem {
  key: string;
  label: string;
  kind: string;
  color: string;
}

export interface WorkflowChainRulesResponse {
  workspace_id: string;
  ruleset: WorkflowChainRuleset;
  catalog: WorkflowAgentCatalogItem[];
}

export const getWorkflowChainRules = (workspace_id: string) =>
  apiGet<WorkflowChainRulesResponse>(`/v1/workflows/chain-rules${qs({ workspace_id })}`);
