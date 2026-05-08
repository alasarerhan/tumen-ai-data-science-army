import { apiGet, qs } from "./client";

export interface DiscoveryAgent {
  name: string;
  description: string;
  category?: string;
  capabilities?: string[];
  cost_tier?: string;
  tags?: string[];
  status?: "healthy" | "degraded" | "offline";
}

export const browseAgents = (workspace_id: string) =>
  apiGet<{ results: DiscoveryAgent[]; total: number }>(
    `/v1/discovery/browse${qs({ workspace_id })}`,
  );
