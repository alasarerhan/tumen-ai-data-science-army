import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import Editor from "@monaco-editor/react";
import cronstrue from "cronstrue";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";
import { Play, Save, Upload, FileCode2, CalendarClock, WandSparkles, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { getCsrfToken } from "../api/client";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";
import { createWorkflow, publishWorkflow } from "../api/workflows";
import { triggerRun } from "../api/runs";
import {
  createScheduledDeployment,
  getWorkflowSchedule,
  pauseScheduledDeployment,
  resumeScheduledDeployment,
  type ScheduledDeployment,
} from "../api/scheduler";
import { ScheduleBadge, formatNextRun } from "../components/workflow/ScheduleBadge";
import { NaturalScheduleInput } from "../components/workflow/NaturalScheduleInput";
import {
  flowToSpec,
  isValidCronExpression,
  specToFlow,
  specToYaml,
  yamlToSpec,
  type WorkflowSpecDocument,
  type WorkflowNodeData,
} from "../utils/workflowDesigner";

const PALETTE_NODES: Array<{ label: string; kind: string; color: string }> = [
  { label: "Data Loader", kind: "eda", color: "#10b981" },
  { label: "Data Cleaner", kind: "eda", color: "#10b981" },
  { label: "Feature Engineering", kind: "ml", color: "#6366f1" },
  { label: "Model Training", kind: "ml", color: "#6366f1" },
  { label: "Narrative", kind: "strategic", color: "#ec4899" },
  { label: "HITL Gate", kind: "hitl", color: "#f59e0b" },
];

const INITIAL_NODES: Node<WorkflowNodeData>[] = [
  {
    id: "n1",
    type: "workflowNode",
    position: { x: 80, y: 100 },
    data: { label: "Data Loader", kind: "eda", status: "success" },
  },
  {
    id: "n2",
    type: "workflowNode",
    position: { x: 360, y: 100 },
    data: { label: "Data Cleaner", kind: "eda", status: "running" },
  },
  {
    id: "n3",
    type: "workflowNode",
    position: { x: 640, y: 100 },
    data: { label: "Model Training", kind: "ml", status: "idle" },
  },
];

const INITIAL_EDGES: Edge[] = [
  { id: "e1", source: "n1", target: "n2", animated: true },
  { id: "e2", source: "n2", target: "n3", animated: true },
];
const SAVE_STATE_RESET_MS = 1500;

function WorkflowNodeCard({ data, selected }: NodeProps<WorkflowNodeData>) {
  const colorByKind: Record<string, string> = {
    eda: "#10b981",
    ml: "#6366f1",
    strategic: "#ec4899",
    hitl: "#f59e0b",
  };

  return (
    <div
      className="min-w-[180px] rounded-md border bg-white px-3 py-2 shadow-sm"
      style={{
        borderColor: selected ? "#6366f1" : "#e2e8f0",
        borderLeftWidth: 4,
        borderLeftColor: colorByKind[data.kind] ?? "#94a3b8",
      }}
    >
      <p className="text-xs font-semibold text-slate-800">{data.label}</p>
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
        <span className="uppercase">{data.kind}</span>
        <span>{data.status ?? "idle"}</span>
      </div>
    </div>
  );
}

function getCronPreview(expression: string): string {
  try {
    return cronstrue.toString(expression, { throwExceptionOnParseError: true });
  } catch {
    return "Invalid cron expression";
  }
}

export default function WorkflowDesigner() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { workspaceId } = useAuth();

  const [flowName, setFlowName] = useState("Sales Intelligence Workflow");
  const [description, setDescription] = useState("Analyze, model, and synthesize strategic recommendations.");
  const [cron, setCron] = useState("0 8 * * 1-5");
  const [naturalSchedule, setNaturalSchedule] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState(INITIAL_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  const [yamlText, setYamlText] = useState("");
  const [yamlDirty, setYamlDirty] = useState(false);
  const [yamlError, setYamlError] = useState<string | null>(null);

  const [savedId, setSavedId] = useState<string | null>(id ?? null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [runState, setRunState] = useState<"idle" | "running">("idle");

  const [scheduleState, setScheduleState] = useState<"idle" | "scheduling" | "scheduled">("idle");
  const [schedule, setSchedule] = useState<ScheduledDeployment | null>(null);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  const nodeTypes = useMemo(() => ({ workflowNode: WorkflowNodeCard }), []);

  const specState = useMemo<{ spec: WorkflowSpecDocument | null; error: string | null }>(() => {
    try {
      const spec = flowToSpec({
        name: flowName,
        description,
        cron,
        nodes,
        edges,
      });
      return { spec, error: null };
    } catch (err: unknown) {
      return {
        spec: null,
        error: err instanceof Error ? err.message : "Invalid workflow specification",
      };
    }
  }, [flowName, description, cron, nodes, edges]);

  const currentSpec = specState.spec;
  const specError = specState.error;
  const cronPreview = getCronPreview(cron);
  const isCronInvalid = !isValidCronExpression(cron);

  useEffect(() => {
    if (yamlDirty || !currentSpec) return;
    setYamlText(specToYaml(currentSpec));
  }, [currentSpec, yamlDirty]);

  useEffect(() => {
    if (!savedId || !workspaceId) return;
    setScheduleLoading(true);
    getWorkflowSchedule(savedId, workspaceId)
      .then(setSchedule)
      .catch((err: unknown) => {
        console.error("Failed to load workflow schedule:", err);
        setSchedule(null);
      })
      .finally(() => setScheduleLoading(false));
  }, [savedId, workspaceId]);

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((existing) => addEdge({ ...connection, id: `e-${Date.now()}` }, existing));
    },
    [setEdges],
  );

  const onDragStart = (event: React.DragEvent<HTMLButtonElement>, label: string, kind: string) => {
    event.dataTransfer.setData("application/workflow-node", JSON.stringify({ label, kind }));
    event.dataTransfer.effectAllowed = "move";
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!reactFlowInstance) return;

    const raw = event.dataTransfer.getData("application/workflow-node");
    if (!raw) return;

    let parsed: { label: string; kind: string } | null = null;
    try {
      parsed = JSON.parse(raw) as { label: string; kind: string };
    } catch {
      return;
    }
    if (!parsed?.label || !parsed?.kind) return;

    const position = reactFlowInstance.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });

    const newNode: Node<WorkflowNodeData> = {
      id: `n-${Date.now()}`,
      type: "workflowNode",
      position,
      data: {
        label: parsed.label,
        kind: parsed.kind,
        status: "idle",
      },
    };

    setNodes((existing) => [...existing, newNode]);
    setYamlDirty(false);
  };

  const handleApplyYaml = () => {
    try {
      const parsed = yamlToSpec(yamlText);
      const transformed = specToFlow(parsed);
      setFlowName(transformed.name);
      setDescription(transformed.description);
      setCron(transformed.cron);
      setNodes(transformed.nodes);
      setEdges(transformed.edges);
      setYamlError(null);
      setYamlDirty(false);
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Invalid YAML");
    }
  };

  const handleFormatYaml = () => {
    try {
      const parsed = yamlToSpec(yamlText);
      setYamlText(specToYaml(parsed));
      setYamlError(null);
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Invalid YAML");
    }
  };

  const handleSaveDraft = async () => {
    if (!workspaceId || !currentSpec) {
      if (specError) setYamlError(specError);
      return;
    }
    setSaveState("saving");
    try {
      const created = await createWorkflow({
        workspace_id: workspaceId,
        name: flowName,
        spec: currentSpec as unknown as Record<string, unknown>,
      });
      setSavedId(created.id);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), SAVE_STATE_RESET_MS);
      setYamlDirty(false);
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Failed to save workflow draft");
      setSaveState("idle");
    }
  };

  const handlePublish = async () => {
    if (!workspaceId || !currentSpec) {
      if (specError) setYamlError(specError);
      return;
    }

    let workflowId = savedId;
    if (!workflowId) {
      try {
        const created = await createWorkflow({
          workspace_id: workspaceId,
          name: flowName,
          spec: currentSpec as unknown as Record<string, unknown>,
          publish: true,
        });
        workflowId = created.id;
        setSavedId(workflowId);
      } catch (err: unknown) {
        setYamlError(err instanceof Error ? err.message : "Failed to publish workflow");
        return;
      }
    } else {
      try {
        await publishWorkflow(workflowId, workspaceId);
      } catch (err: unknown) {
        setYamlError(err instanceof Error ? err.message : "Failed to publish workflow");
        return;
      }
    }

    navigate("/workflows");
  };

  const handleRun = async () => {
    if (!workspaceId || !currentSpec) {
      if (specError) setYamlError(specError);
      return;
    }
    setRunState("running");
    try {
      const run = await triggerRun({
        workspace_id: workspaceId,
        flow_key: savedId ?? flowName,
        parameters: {
          spec: currentSpec,
        },
      });
      navigate(`/runs/${run.id}`);
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Failed to trigger workflow run");
      setRunState("idle");
    }
  };

  const handleSchedule = async () => {
    if (!workspaceId || !savedId || isCronInvalid) {
      setYamlError("Save the workflow and provide a valid cron expression to schedule");
      return;
    }
    setScheduleState("scheduling");
    try {
      const result = await createScheduledDeployment(savedId, {
        workspace_id: workspaceId,
        cron,
        timezone: "UTC",
      });
      setSchedule({
        deployment_id: result.deployment_id,
        deployment_name: result.deployment_name,
        workflow_spec_id: result.workflow_spec_id,
        cron: result.cron,
        timezone: result.timezone,
        enabled: result.enabled,
        next_run_at: null,
        last_run_at: null,
        last_run_status: null,
      });
      setScheduleState("scheduled");
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Failed to create schedule");
      setScheduleState("idle");
    }
  };

  const handleToggleSchedule = async () => {
    if (!workspaceId || !schedule) return;
    setScheduleLoading(true);
    try {
      if (schedule.enabled) {
        await pauseScheduledDeployment(schedule.deployment_id, workspaceId);
        setSchedule((prev) => prev ? { ...prev, enabled: false } : null);
      } else {
        await resumeScheduledDeployment(schedule.deployment_id, workspaceId);
        setSchedule((prev) => prev ? { ...prev, enabled: true } : null);
      }
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Failed to toggle schedule");
    } finally {
      setScheduleLoading(false);
    }
  };

  const handleScheduleChange = (naturalValue: string, cronValue: string) => {
    if (naturalValue) {
      setNaturalSchedule(naturalValue);
      setCron("");
    } else if (cronValue) {
      setCron(cronValue);
      setNaturalSchedule("");
    }
  };

  const parseNaturalSchedule = async () => {
    if (!naturalSchedule) return;
    try {
      const csrf = await getCsrfToken();
      const response = await fetch("/v1/scheduler/parse", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ expression: naturalSchedule }),
      });
      if (!response.ok) throw new Error("Failed to parse schedule");
      const data = await response.json();
      setCron(data.cron);
      setNaturalSchedule("");
    } catch (err: unknown) {
      setYamlError(err instanceof Error ? err.message : "Failed to parse natural schedule");
    }
  };

  return (
    <div className="flex h-screen w-screen flex-col overflow-hidden bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-400">Workflow Designer</p>
          <h1 className="text-sm font-semibold text-slate-800">{flowName}</h1>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<Save size={13} />}
            loading={saveState === "saving"}
            disabled={!currentSpec}
            onClick={() => {
              void handleSaveDraft();
            }}
          >
            {saveState === "saved" ? "Saved" : "Save Draft"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={<Upload size={13} />}
            disabled={!currentSpec}
            onClick={() => void handlePublish()}
          >
            Publish
          </Button>
          <Button
            variant="secondary"
            size="sm"
            leadingIcon={
              scheduleState === "scheduling" ? (
                <Loader2 size={13} className="animate-spin" />
              ) : (
                <CalendarClock size={13} />
              )
            }
            disabled={!currentSpec || !savedId || isCronInvalid}
            loading={scheduleState === "scheduling"}
            onClick={() => void handleSchedule()}
          >
            {schedule ? "Update Schedule" : "Schedule"}
          </Button>
          <Button
            variant="primary"
            size="sm"
            leadingIcon={<Play size={13} />}
            loading={runState === "running"}
            disabled={!currentSpec}
            onClick={() => {
              void handleRun();
            }}
          >
            Run
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[220px_1fr_420px]">
        <aside className="border-r border-slate-200 bg-white p-3">
          <div className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Nodes</p>
            {PALETTE_NODES.map((node) => (
              <button
                key={`${node.kind}-${node.label}`}
                type="button"
                draggable
                onDragStart={(event) => onDragStart(event, node.label, node.kind)}
                className="flex w-full items-center justify-between rounded-md border border-slate-200 px-2 py-2 text-left text-xs hover:bg-slate-50"
              >
                <span>{node.label}</span>
                <span className="size-2 rounded-full" style={{ backgroundColor: node.color }} />
              </button>
            ))}
          </div>
        </aside>

        <section className="min-h-0" onDrop={onDrop} onDragOver={(event) => event.preventDefault()}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onInit={setReactFlowInstance}
            fitView
          >
            <Background gap={20} size={1} />
            <MiniMap pannable zoomable />
            <Controls />
          </ReactFlow>
        </section>

        <aside className="flex min-h-0 flex-col border-l border-slate-200 bg-white">
          <div className="space-y-2 border-b border-slate-200 p-3">
            <label className="text-xs font-medium text-slate-600">Workflow name</label>
            <input
              value={flowName}
              onChange={(event) => setFlowName(event.target.value)}
              className="h-8 w-full rounded border border-slate-300 px-2 text-sm"
            />
            <label className="text-xs font-medium text-slate-600">Description</label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
              className="w-full resize-none rounded border border-slate-300 px-2 py-1 text-sm"
            />
          </div>

          <div className="space-y-3 border-b border-slate-200 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <CalendarClock size={13} />
              Schedule
            </div>
            <NaturalScheduleInput
              value={naturalSchedule}
              cronValue={cron}
              onChange={handleScheduleChange}
              disabled={false}
            />
            {naturalSchedule && (
              <Button variant="secondary" size="xs" onClick={parseNaturalSchedule}>
                Parse to Cron
              </Button>
            )}
            <p className={`text-xs ${isCronInvalid ? "text-red-500" : "text-slate-500"}`}>
              {cronPreview}
            </p>
            {schedule && (
              <div className="mt-2">
                <ScheduleBadge
                  cron={schedule.cron}
                  enabled={schedule.enabled}
                  nextRunAt={schedule.next_run_at}
                  onToggle={handleToggleSchedule}
                />
              </div>
            )}
          </div>

          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              <FileCode2 size={13} /> YAML
            </div>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="xs" leadingIcon={<WandSparkles size={12} />} onClick={handleFormatYaml}>
                Format
              </Button>
              <Button variant="secondary" size="xs" onClick={handleApplyYaml}>
                Apply
              </Button>
            </div>
          </div>

          <div className="min-h-0 flex-1">
            <Editor
              language="yaml"
              value={yamlText}
              onChange={(value) => {
                setYamlText(value ?? "");
                setYamlDirty(true);
              }}
              options={{
                minimap: { enabled: false },
                fontSize: 12,
                wordWrap: "on",
              }}
              height="100%"
            />
          </div>
          {specError ? <p className="border-t border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">{specError}</p> : null}
          {yamlError ? <p className="border-t border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{yamlError}</p> : null}
        </aside>
      </div>
    </div>
  );
}
