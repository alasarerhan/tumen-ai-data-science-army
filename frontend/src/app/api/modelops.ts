import { apiGet, qs } from "./client";

export interface ModelRegistryEntry {
  model_id: string;
  version: string;
  stage: string;
  artifact_id: string;
  workflow_run_id: string | null;
  produced_by_node_id: string | null;
  parent_artifact_ids: string[];
  uri_scheme: string;
  created_at: string | null;
  approval_state: string;
  deployment_state: string;
  monitoring_status: string;
  latest_metric_artifact_ids: string[];
  drift_status: string;
  performance_status: string;
  retrain_candidate: boolean;
}

export interface ModelMonitorSnapshot {
  monitor_id: string;
  artifact_id: string;
  kind: string;
  workflow_run_id: string | null;
  produced_by_node_id: string | null;
  parent_artifact_ids: string[];
  uri_scheme: string;
  created_at: string | null;
  freshness: string;
  drift_status: string;
  performance_status: string;
  alert_policy: string;
}

export interface RetrainCandidate {
  model_id: string;
  version: string;
  reason: string;
  drift_status: string;
  performance_status: string;
  linked_monitor_ids: string[];
  suggested_workflow: string;
  action_state: string;
}

export interface ModelOpsSummary {
  registry: ModelRegistryEntry[];
  monitors: ModelMonitorSnapshot[];
  retrain_candidates: RetrainCandidate[];
  metrics: {
    registered_models: number;
    monitor_snapshots: number;
    retrain_candidates: number;
    deployments: number;
  };
  status: {
    registry: string;
    monitoring: string;
    deployment: string;
    retraining: string;
  };
}

export const getModelOpsSummary = (workspace_id: string) =>
  apiGet<ModelOpsSummary>(`/v1/modelops/summary${qs({ workspace_id })}`);
