import { apiGet, apiPost, qs } from "./client";

export interface PlatformResourceDescriptor {
  resource_key: string;
  label: string;
  scope: "user" | "workspace" | "tenant" | "admin" | "system";
  required_role: "member" | "workspace_admin" | "tenant_admin" | "system";
  queryable_fields: string[];
  available_actions: string[];
  canonical_ui: string | null;
  not_exposed_reason: string | null;
}

export interface PlatformActionPlan {
  action_name: string;
  resource_key: string;
  risk_level: "low" | "medium" | "high";
  confirmation_required: boolean;
  allowed: boolean;
  summary: string;
  arguments: Record<string, unknown>;
  missing_arguments: string[];
  denial_reason: string | null;
}

export interface PlatformActionResult {
  status: "planned" | "executed" | "denied" | "missing_arguments" | "conflict" | "error";
  action_name: string;
  summary: string;
  data: Record<string, unknown>;
  audit_id: string | null;
}

export interface PlatformEntityRef {
  resource_key: string;
  entity_id: string;
  label: string;
  href: string | null;
}

export interface PlatformRelationship {
  source: PlatformEntityRef;
  target: PlatformEntityRef;
  relationship_type: string;
}

export interface PlatformQuerySection {
  resource_key: string;
  label: string;
  status: "ok" | "empty" | "access_denied" | "not_configured" | "error";
  message: string | null;
  columns: string[];
  records: Array<Record<string, unknown>>;
  metrics: Record<string, unknown>;
  links: Array<{ label: string; href: string }>;
  relationships: PlatformRelationship[];
  provenance: {
    resource_key: string;
    resolver: string;
    generated_at: string;
    filters: Record<string, unknown>;
    redactions: string[];
  };
}

export interface PlatformQueryResultArtifact {
  type: "platform_query_result";
  summary: string;
  query: string;
  plan: {
    query: string;
    resource_keys: string[];
    filters: Record<string, unknown>;
    limit: number;
  };
  sections: PlatformQuerySection[];
  action_plan?: PlatformActionPlan | null;
}

export const getControlPlaneCatalog = (workspace_id: string) =>
  apiGet<{ items: PlatformResourceDescriptor[] }>(`/v1/control-plane/catalog${qs({ workspace_id })}`);

export const queryControlPlane = (body: {
  workspace_id: string;
  query: string;
  resource_keys?: string[];
  limit?: number;
  filters?: Record<string, unknown>;
}) => apiPost<PlatformQueryResultArtifact>("/v1/control-plane/query", body);

export const planControlPlaneAction = (body: {
  workspace_id: string;
  action_name?: string;
  query?: string;
  arguments?: Record<string, unknown>;
}) => apiPost<PlatformActionPlan>("/v1/control-plane/actions/plan", body);

export const executeControlPlaneAction = (body: {
  workspace_id: string;
  action_name: string;
  arguments?: Record<string, unknown>;
  confirmed?: boolean;
}) => apiPost<PlatformActionResult>("/v1/control-plane/actions/execute", body);
