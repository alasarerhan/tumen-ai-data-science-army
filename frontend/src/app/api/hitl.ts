import { apiGet, apiPost, qs } from "./client";

export interface HitlApproval {
  id: string;
  workspace_id: string;
  tenant_id: string;
  workflow_run_id: string | null;
  step_key: string;
  payload: Record<string, unknown>;
  status: "pending" | "approved" | "rejected" | "expired";
  comment: string | null;
  reviewed_at: string | null;
  expires_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const getHitlItems = (params: { workspace_id: string; status?: string }) =>
  apiGet<{ items: HitlApproval[] }>(`/v1/hitl${qs(params)}`);

export const getHitlItem = (id: string, workspace_id: string) =>
  apiGet<HitlApproval>(`/v1/hitl/${id}${qs({ workspace_id })}`);

export const approveHitl = (id: string, body: { workspace_id: string; comment?: string }) =>
  apiPost<HitlApproval>(`/v1/hitl/${id}/approve`, body);

export const rejectHitl = (id: string, body: { workspace_id: string; reason?: string }) =>
  apiPost<HitlApproval>(`/v1/hitl/${id}/reject`, body);

