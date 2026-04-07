import { BASE_URL, qs } from "./client";

export function buildRunLogsStreamUrl(run_id: string, workspace_id: string): string {
  return `${BASE_URL}/v1/runs/${run_id}/logs${qs({ workspace_id })}`;
}

