import { apiGet, apiPost, qs } from "./client";

export interface ScheduledDeployment {
  deployment_id: string;
  deployment_name: string;
  workflow_spec_id: string;
  cron: string;
  timezone: string;
  enabled: boolean;
  next_run_at: string | null;
  last_run_at: string | null;
  last_run_status: string | null;
}

export interface ScheduleWorkflowResponse {
  deployment_id: string;
  deployment_name: string;
  cron: string;
  timezone: string;
  enabled: boolean;
  workflow_spec_id: string;
}

export const createScheduledDeployment = (
  workflow_id: string,
  body: {
    workspace_id: string;
    cron: string;
    timezone?: string;
  },
) =>
  apiPost<ScheduleWorkflowResponse>(
    `/v1/workflows/${workflow_id}/schedule${qs({ workspace_id: body.workspace_id })}`,
    { cron: body.cron, timezone: body.timezone },
  );

export const listScheduledDeployments = (workspace_id: string) =>
  apiGet<{ items: ScheduledDeployment[] }>(
    `/v1/workflows/schedules${qs({ workspace_id })}`,
  );

export const getWorkflowSchedule = (workflow_id: string, workspace_id: string) =>
  apiGet<ScheduledDeployment>(
    `/v1/workflows/${workflow_id}/schedule${qs({ workspace_id })}`,
  );

export const pauseScheduledDeployment = (deployment_id: string, workspace_id: string) =>
  apiPost<{ deployment_id: string; status: string }>(
    `/v1/workflows/schedules/${deployment_id}/pause${qs({ workspace_id })}`,
  );

export const resumeScheduledDeployment = (deployment_id: string, workspace_id: string) =>
  apiPost<{ deployment_id: string; status: string }>(
    `/v1/workflows/schedules/${deployment_id}/resume${qs({ workspace_id })}`,
  );

export const triggerScheduledWorkflow = (
  workflow_spec_id: string,
  workspace_id: string,
  parameters?: Record<string, unknown>,
) =>
  apiPost<{ flow_run_id: string; status: string }>(
    `/v1/workflows/${workflow_spec_id}/trigger${qs({ workspace_id })}`,
    { parameters },
  );
