import type { WorkflowSpec, WorkflowValidationSummary } from "../api/workflows";

type WorkflowValidationStatus = WorkflowValidationSummary["status"];

export function getWorkflowValidationVariant(
  status: WorkflowValidationStatus,
): "success" | "warning" | "danger" {
  switch (status) {
    case "invalid":
      return "danger";
    case "advisory":
      return "warning";
    default:
      return "success";
  }
}

export function getWorkflowValidationLabel(status: WorkflowValidationStatus): string {
  switch (status) {
    case "invalid":
      return "Invalid Chain";
    case "advisory":
      return "Advisory Chain";
    default:
      return "Chain Safe";
  }
}

/** @internal Resolves a workflow spec by flow key, used only within this module. */
export function resolveWorkflowForFlowKey(
  workflows: WorkflowSpec[],
  flowKey: string | null | undefined,
): WorkflowSpec | null {
  if (!flowKey) return null;
  return workflows.find((workflow) => workflow.id === flowKey || workflow.name === flowKey) ?? null;
}

export function resolveWorkflowValidationForFlowKey(
  workflows: WorkflowSpec[],
  flowKey: string | null | undefined,
): WorkflowValidationSummary | null {
  return resolveWorkflowForFlowKey(workflows, flowKey)?.validation_summary ?? null;
}
