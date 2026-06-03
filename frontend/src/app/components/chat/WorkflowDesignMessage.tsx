import { useMemo, useState } from "react";
import { Check, Edit, X, CalendarClock, Users } from "lucide-react";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { useAuth } from "../../context/AuthContext";
import { useWorkflowChainRules } from "../../hooks/useWorkflowChainRules";
import { inspectWorkflowSpec } from "../../utils/workflowChainValidator";

interface WorkflowStep {
  id: string;
  agent: string;
  instruction: string;
  depends_on?: string[];
  fallbacks?: string[];
}

interface WorkflowSpec {
  name: string;
  description?: string;
  steps: WorkflowStep[];
  schedule?: {
    cron?: string;
    natural_language?: string;
    timezone?: string;
  };
  hitl_config?: {
    approval_gates: string[];
    confidence_threshold: number;
  };
}

interface WorkflowDesignMessageProps {
  workflowSpec: WorkflowSpec;
  onApprove: () => void;
  onModify: (feedback: string) => void;
  onCancel: () => void;
}

export function WorkflowDesignMessage({
  workflowSpec,
  onApprove,
  onModify,
  onCancel,
}: WorkflowDesignMessageProps) {
  const { workspaceId } = useAuth();
  const workflowChainRulesQuery = useWorkflowChainRules(workspaceId);
  const [modifyMode, setModifyMode] = useState(false);
  const [feedback, setFeedback] = useState("");
  const validation = useMemo(
    () =>
      inspectWorkflowSpec({
        name: workflowSpec.name,
        description: workflowSpec.description,
        steps: workflowSpec.steps.map((step) => ({
          id: step.id,
          agent: step.agent,
          instruction: step.instruction,
          depends_on: step.depends_on ?? [],
        })),
      }, workflowChainRulesQuery.data?.ruleset),
    [workflowSpec, workflowChainRulesQuery.data?.ruleset],
  );
  const errorMessages = validation.errors.map((issue) => issue.message);
  const warningMessages = validation.warnings.map((issue) => issue.message);

  const handleModifySubmit = () => {
    onModify(feedback);
    setModifyMode(false);
    setFeedback("");
  };

  const handleCancelModify = () => {
    setModifyMode(false);
    setFeedback("");
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">
          Proposed Workflow: {workflowSpec.name}
        </h3>
        <Badge variant="warning" className="border border-amber-200">
          Draft
        </Badge>
      </div>

      {workflowSpec.description && (
        <p className="mb-3 text-xs text-slate-600">{workflowSpec.description}</p>
      )}

      {errorMessages.length > 0 && (
        <div className="mb-4 rounded border border-rose-200 bg-rose-50 p-2">
          <p className="text-xs font-medium text-rose-800">Invalid workflow chain</p>
          {errorMessages.map((message) => (
            <p key={message} className="mt-1 text-xs text-rose-700">
              {message}
            </p>
          ))}
        </div>
      )}

      {warningMessages.length > 0 && (
        <div className="mb-4 rounded border border-amber-200 bg-amber-50 p-2">
          <p className="text-xs font-medium text-amber-800">Workflow warnings</p>
          {warningMessages.map((message) => (
            <p key={message} className="mt-1 text-xs text-amber-700">
              {message}
            </p>
          ))}
        </div>
      )}

      <div className="mb-4 space-y-2">
        <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
          Steps
        </p>
        {workflowSpec.steps.map((step, index) => (
          <div
            key={step.id}
            className="flex items-start gap-2 rounded bg-slate-50 p-2"
          >
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-medium text-indigo-600">
              {index + 1}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-slate-700">{step.agent}</p>
              <p className="truncate text-xs text-slate-500">{step.instruction}</p>
            </div>
          </div>
        ))}
      </div>

      {workflowSpec.schedule && (
        <div className="mb-4 flex items-start gap-2 rounded bg-amber-50 p-2">
          <CalendarClock size={14} className="mt-0.5 shrink-0 text-amber-600" />
          <div>
            <p className="text-xs font-medium text-amber-800">Schedule</p>
            <p className="text-xs text-amber-600">
              {workflowSpec.schedule.natural_language || workflowSpec.schedule.cron}
            </p>
          </div>
        </div>
      )}

      {workflowSpec.hitl_config && workflowSpec.hitl_config.approval_gates.length > 0 && (
        <div className="mb-4 flex items-start gap-2 rounded bg-blue-50 p-2">
          <Users size={14} className="mt-0.5 shrink-0 text-blue-600" />
          <div>
            <p className="text-xs font-medium text-blue-800">Human-in-the-Loop</p>
            <p className="text-xs text-blue-600">
              Approval gates: {workflowSpec.hitl_config.approval_gates.join(", ")}
            </p>
          </div>
        </div>
      )}

      {modifyMode ? (
        <div className="space-y-2">
          <textarea
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="Describe what you want to change..."
            className="w-full resize-none rounded-md border border-slate-300 p-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            rows={3}
            autoFocus
          />
          <div className="flex gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={handleModifySubmit}
              disabled={!feedback.trim()}
            >
              Submit Changes
            </Button>
            <Button variant="ghost" size="sm" onClick={handleCancelModify}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            size="sm"
            leadingIcon={<Check size={14} />}
            onClick={onApprove}
            disabled={errorMessages.length > 0}
          >
            Approve & Run
          </Button>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<Edit size={14} />}
            onClick={() => setModifyMode(true)}
          >
            Modify
          </Button>
          <Button
            variant="ghost"
            size="sm"
            leadingIcon={<X size={14} />}
            onClick={onCancel}
          >
            Cancel
          </Button>
        </div>
      )}
    </div>
  );
}
