import { BASE_URL, apiGet, apiPost, qs } from "./client";

export interface SignalDto {
  id: string;
  workflow_run_id: string;
  signal_type:
    | "pause"
    | "resume"
    | "skip"
    | "modify"
    | "annotate"
    | "cancel"
    | "node_started"
    | "node_progress"
    | "node_succeeded"
    | "node_failed"
    | "artifact_created"
    | "approval_required"
    | "run_completed";
  target_step: string | null;
  note: string | null;
  payload: Record<string, unknown>;
  created_by_user_id: string | null;
  created_at: string;
}

export type SignalStreamEvent =
  | { type: "message"; id: string; message: SignalDto }
  | { type: "done"; id?: string }
  | { type: "error"; id?: string; error: string };

export const emitSignal = (
  run_id: string,
  body: {
    workspace_id: string;
    signal_type: SignalDto["signal_type"];
    target_step?: string;
    note?: string;
    payload?: Record<string, unknown>;
  },
) => apiPost<SignalDto>(`/v1/runs/${run_id}/signals`, body);

export const listSignals = (run_id: string, workspace_id: string) =>
  apiGet<{ items: SignalDto[] }>(`/v1/runs/${run_id}/signals${qs({ workspace_id })}`);

export function buildSignalStreamUrl(
  run_id: string,
  workspace_id: string,
  last_event_id?: string,
): string {
  const params: Record<string, string> = { workspace_id };
  if (last_event_id) {
    params.last_event_id = last_event_id;
  }
  return `${BASE_URL}/v1/runs/${run_id}/signals/stream${qs(params)}`;
}
