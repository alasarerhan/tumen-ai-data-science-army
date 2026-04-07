import { apiGet } from "./client";

export interface MeResponse {
  id: string;
  sub: string;
  email: string | null;
  tenant_memberships: Array<{ tenant_id: string; role: string }>;
  workspace_memberships: Array<{ workspace_id: string; role: string }>;
  claims: Record<string, unknown>;
}

export const getMe = () => apiGet<MeResponse>("/v1/me");

