import { useCallback, useEffect, useMemo, useState } from "react";
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
import { Play, Save, Upload, FileCode2, CalendarClock, WandSparkles, Loader2, Search, History, CheckCircle2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { withCsrfHeader } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { createWorkflow, publishWorkflow } from "../api/workflows";
import { getWorkflowNodeTypes, type WorkflowNodeType } from "../api/workflowNodeTypes";
import { triggerRun } from "../api/runs";
import {
  createScheduledDeployment,
  getWorkflowSchedule,
  pauseScheduledDeployment,
  resumeScheduledDeployment,
  type ScheduledDeployment,
} from "../api/scheduler";
import { ScheduleBadge } from "../components/workflow/ScheduleBadge";
import { NaturalScheduleInput } from "../components/workflow/NaturalScheduleInput";
import { useToast } from "../hooks/useToast";
import {
  flowToSpec,
  inspectWorkflowGraphSpec,
  isValidCronExpression,
  specToFlow,
  specToYaml,
  yamlToSpec,
  type WorkflowSpecDocument,
  type WorkflowNodeData,
} from "../utils/workflowDesigner";
import { getWorkflowAgentCatalog } from "../utils/workflowChainValidator";
import { useWorkflowChainRules } from "../hooks/useWorkflowChainRules";

const PALETTE_NODE_KEYS = [
  "DataLoaderToolsAgent",
  "DataCleaningAgent",
  "DataWranglingAgent",
  "EDAToolsAgent",
  "DataVisualizationAgent",
  "FeatureEngineeringAgent",
  "H2OMLAgent",
  "NarrativeAgent",
  "ApprovalGateAgent",
];

const INITIAL_NODES: Node<WorkflowNodeData>[] = [
  {
    id: "n1",
    type: "workflowNode",
    position: { x: 80, y: 100 },
    data: { label: "Data Loader", kind: "data", agent: "DataLoaderToolsAgent", status: "success" },
  },
  {
    id: "n2",
    type: "workflowNode",
    position: { x: 360, y: 100 },
    data: { label: "Data Cleaning", kind: "data", agent: "DataCleaningAgent", status: "running" },
  },
  {
    id: "n3",
    type: "workflowNode",
    position: { x: 640, y: 100 },
    data: { label: "Feature Engineering", kind: "ml", agent: "FeatureEngineeringAgent", status: "idle" },
  },
  {
    id: "n4",
    type: "workflowNode",
    position: { x: 920, y: 100 },
    data: { label: "H2O ML", kind: "ml", agent: "H2OMLAgent", status: "idle" },
  },
];

const INITIAL_EDGES: Edge[] = [
  { id: "e1", source: "n1", target: "n2", animated: true },
  { id: "e2", source: "n2", target: "n3", animated: true },
  { id: "e3", source: "n3", target: "n4", animated: true },
];
const SAVE_STATE_RESET_MS = 1500;

function WorkflowNodeCard({ data, selected }: NodeProps<WorkflowNodeData>) {
  const colorByKind: Record<string, string> = {
    data: "#10b981",
    analysis: "#0ea5e9",
    ml: "#6366f1",
    strategic: "#ec4899",
    hitl: "#f59e0b",
    orchestration: "#64748b",
    ops: "#7c3aed",
    timeseries: "#0f766e",
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
  const toast = useToast();
  const workflowChainRulesQuery = useWorkflowChainRules(workspaceId);
  const workflowChainRules = workflowChainRulesQuery.data?.ruleset;

  const [flowName, setFlowName] = useState("Sales Intelligence Workflow");
  const [description, setDescription] = useState("Analyze, model, and synthesize strategic recommendations.");
  const [cron, setCron] = useState("0 8 * * 1-5");
  const [naturalSchedule, setNaturalSchedule] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState(INITIAL_NODES);
  const [edges, setEdges, onEdgesChange] = useEdgesState(INITIAL_EDGES);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [catalogSearch, setCatalogSearch] = useState("");
  const [nodeTypeCatalog, setNodeTypeCatalog] = useState<WorkflowNodeType[]>([]);

  const [yamlText, setYamlText] = useState("");
  const [yamlDirty, setYamlDirty] = useState(false);
  const [yamlError, setYamlError] = useState<string | null>(null);

  const [savedId, setSavedId] = useState<string | null>(id ?? null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [runState, setRunState] = useState<"idle" | "running">("idle");

  const [scheduleState, setScheduleState] = useState<"idle" | "scheduling" | "scheduled">("idle");
  const [schedule, setSchedule] = useState<ScheduledDeployment | null>(null);

  const nodeTypes = useMemo(() => ({ workflowNode: WorkflowNodeCard }), []);
  const paletteNodes = useMemo(
    () => getWorkflowAgentCatalog(workflowChainRules).filter((node) => PALETTE_NODE_KEYS.includes(node.key)),
    [workflowChainRules],
  );
  const paletteItems = useMemo(() => {
    if (nodeTypeCatalog.length > 0) {
      return nodeTypeCatalog
        .filter((node) => !node.type.endsWith(".trigger"))
        .map((node) => ({
          label: node.label,
          kind: node.category.toLowerCase().replace(/\s+/g, "_"),
          agent: node.type,
          nodeType: node.type,
          color: node.ui.color,
          description: node.description,
          inputs: node.inputs,
          outputs: node.outputs,
          timeout_seconds: node.timeout_seconds,
          retry_policy: node.retry_policy,
        }));
    }
    return paletteNodes.map((node) => ({
      label: node.label,
      kind: node.kind,
      agent: node.key,
      nodeType: undefined,
      color: node.color,
      description: "",
      inputs: [],
      outputs: [],
      timeout_seconds: undefined,
      retry_policy: undefined,
    }));
  }, [nodeTypeCatalog, paletteNodes]);
  const visiblePaletteItems = useMemo(() => {
    const query = catalogSearch.trim().toLowerCase();
    if (!query) return paletteItems;
    return paletteItems.filter((item) =>
      `${item.label} ${item.kind} ${item.nodeType ?? ""} ${item.description}`.toLowerCase().includes(query),
    );
  }, [catalogSearch, paletteItems]);
  const selectedNode = useMemo(() => nodes.find((node) => node.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);

  const specState = useMemo<{ spec: WorkflowSpecDocument | null; error: string | null; warnings: string[] }>(() => {
    try {
      const spec = flowToSpec({
        name: flowName,
        description,
        cron,
        nodes,
        edges,
      }, workflowChainRules);
      const inspection = inspectWorkflowGraphSpec(spec, workflowChainRules);
      return {
        spec,
        error: null,
        warnings: inspection.warnings.map((issue) => issue.message),
      };
    } catch (err: unknown) {
      return {
        spec: null,
        error: err instanceof Error ? err.message : "Invalid workflow specification",
        warnings: [],
      };
    }
  }, [flowName, description, cron, nodes, edges, workflowChainRules]);

  const currentSpec = specState.spec;
  const specError = specState.error;
  const specWarnings = specState.warnings;
  const cronPreview = getCronPreview(cron);
  const isCronInvalid = !isValidCronExpression(cron);

  useEffect(() => {
    if (yamlDirty || !currentSpec) return;
    setYamlText(specToYaml(currentSpec));
  }, [currentSpec, yamlDirty]);

  useEffect(() => {
    if (!savedId || !workspaceId) return;
    getWorkflowSchedule(savedId, workspaceId)
      .then(setSchedule)
      .catch((err: unknown) => {
        console.error("Failed to load workflow schedule:", err);
        setSchedule(null);
      });
  }, [savedId, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;
    getWorkflowNodeTypes(workspaceId)
      .then((result) => setNodeTypeCatalog(result.items))
      .catch((err: unknown) => {
        console.error("Failed to load workflow node catalog:", err);
      });
  }, [workspaceId]);

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target || connection.source === connection.target) {
        toast.error("Invalid edge", "Connect two different workflow nodes.");
        return;
      }
      if (edges.some((edge) => edge.source === connection.source && edge.target === connection.target)) {
        toast.info("Connection exists", "That workflow path is already connected.");
        return;
      }
      setEdges((existing) => addEdge({ ...connection, id: `e-${Date.now()}` }, existing));
    },
    [edges, setEdges, toast],
  );

  const onDragStart = (
    event: React.DragEvent<HTMLButtonElement>,
    item: {
      label: string;
      kind: string;
      agent: string;
      nodeType?: string;
      inputs?: Array<{ name: string; artifact_type: string; required: boolean }>;
      outputs?: Array<{ name: string; artifact_type: string; required: boolean }>;
      timeout_seconds?: number;
      retry_policy?: { max_attempts: number; backoff_seconds: number };
    },
  ) => {
    event.dataTransfer.setData("application/workflow-node", JSON.stringify(item));
    event.dataTransfer.effectAllowed = "move";
  };

  const onDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!reactFlowInstance) return;

    const raw = event.dataTransfer.getData("application/workflow-node");
    if (!raw) return;

    let parsed: {
      label: string;
      kind: string;
      agent: string;
      nodeType?: string;
      inputs?: Array<{ name: string; artifact_type: string; required: boolean }>;
      outputs?: Array<{ name: string; artifact_type: string; required: boolean }>;
      timeout_seconds?: number;
      retry_policy?: { max_attempts: number; backoff_seconds: number };
    } | null = null;
    try {
      parsed = JSON.parse(raw) as { label: string; kind: string; agent: string };
    } catch {
      return;
    }
    if (!parsed?.label || !parsed?.kind || !parsed?.agent) return;

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
        agent: parsed.agent,
        nodeType: parsed.nodeType,
        inputs: parsed.inputs,
        outputs: parsed.outputs,
        timeout_seconds: parsed.timeout_seconds,
        retry_policy: parsed.retry_policy,
        status: "idle",
      },
    };

    setNodes((existing) => [...existing, newNode]);
    setYamlDirty(false);
  };

  const handleApplyYaml = () => {
    try {
      const parsed = yamlToSpec(yamlText, workflowChainRules);
      const transformed = specToFlow(parsed, workflowChainRules);
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
      const parsed = yamlToSpec(yamlText, workflowChainRules);
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
      toast.success("Workflow saved", "Draft changes were stored successfully.");
      setTimeout(() => setSaveState("idle"), SAVE_STATE_RESET_MS);
      setYamlDirty(false);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to save workflow draft";
      setYamlError(message);
      toast.error("Save failed", message);
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
        toast.success("Workflow published", "A new published version was created.");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to publish workflow";
        setYamlError(message);
        toast.error("Publish failed", message);
        return;
      }
    } else {
      try {
        await publishWorkflow(workflowId, workspaceId);
        toast.success("Workflow published", "The existing draft is now live.");
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Failed to publish workflow";
        setYamlError(message);
        toast.error("Publish failed", message);
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
        workflow_spec_id: savedId ?? undefined,
        trigger_type: "manual",
        input_artifact_ids: [],
        parameters: {
          spec: currentSpec,
        },
      });
      toast.success("Run started", `Run ${run.id} is now in progress.`);
      navigate(`/runs/${run.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to trigger workflow run";
      setYamlError(message);
      toast.error("Run failed to start", message);
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
      toast.success("Schedule updated", "The workflow schedule was saved.");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create schedule";
      setYamlError(message);
      toast.error("Schedule failed", message);
      setScheduleState("idle");
    }
  };

  const handleToggleSchedule = async () => {
    if (!workspaceId || !schedule) return;
    try {
      if (schedule.enabled) {
        await pauseScheduledDeployment(schedule.deployment_id, workspaceId);
        setSchedule((prev) => prev ? { ...prev, enabled: false } : null);
        toast.info("Schedule paused");
      } else {
        await resumeScheduledDeployment(schedule.deployment_id, workspaceId);
        setSchedule((prev) => prev ? { ...prev, enabled: true } : null);
        toast.success("Schedule resumed");
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to toggle schedule";
      setYamlError(message);
      toast.error("Schedule update failed", message);
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
      const headers = await withCsrfHeader({
        "Content-Type": "application/json",
      });
      const response = await fetch("/v1/scheduler/parse", {
        method: "POST",
        credentials: "include",
        headers,
        body: JSON.stringify({ expression: naturalSchedule }),
      });
      if (!response.ok) throw new Error("Failed to parse schedule");
      const data = await response.json();
      setCron(data.cron);
      setNaturalSchedule("");
      toast.success("Natural language schedule parsed", data.cron);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to parse natural schedule";
      setYamlError(message);
      toast.error("Schedule parse failed", message);
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
            leadingIcon={<History size={13} />}
            disabled={!savedId}
            onClick={() => savedId && navigate(`/workflows/${savedId}`)}
          >
            History
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
            Test Run
          </Button>
        </div>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[220px_1fr_420px]">
        <aside className="border-r border-slate-200 bg-white p-3">
          <div className="space-y-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Node Catalog</p>
              <div className="mt-2 flex h-8 items-center gap-2 rounded border border-slate-200 px-2">
                <Search size={13} className="text-slate-400" />
                <input
                  value={catalogSearch}
                  onChange={(event) => setCatalogSearch(event.target.value)}
                  placeholder="Search nodes"
                  className="min-w-0 flex-1 text-xs outline-none"
                />
              </div>
            </div>
            {visiblePaletteItems.map((node) => (
              <button
                key={`${node.kind}-${node.label}-${node.nodeType ?? node.agent}`}
                type="button"
                draggable
                onDragStart={(event) => onDragStart(event, node)}
                className="w-full rounded-md border border-slate-200 px-2 py-2 text-left text-xs hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="font-medium text-slate-700">{node.label}</span>
                  <span className="size-2 rounded-full" style={{ backgroundColor: node.color }} />
                </span>
                <span className="mt-1 block truncate text-[11px] text-slate-500">{node.nodeType ?? node.agent}</span>
              </button>
            ))}
            {visiblePaletteItems.length === 0 ? <p className="text-xs text-slate-500">No matching nodes.</p> : null}
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
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            fitView
          >
            <Background gap={20} size={1} />
            <MiniMap pannable zoomable />
            <Controls />
          </ReactFlow>
        </section>

        <aside className="flex min-h-0 flex-col border-l border-slate-200 bg-white">
          <div className="space-y-2 border-b border-slate-200 p-3">
            <div className="flex items-center justify-between">
              <span className="rounded bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">Draft</span>
              <span className={`flex items-center gap-1 text-[11px] ${specError || yamlError ? "text-red-600" : "text-emerald-600"}`}>
                <CheckCircle2 size={12} /> {specError || yamlError ? "Invalid" : "Valid"}
              </span>
            </div>
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

          <div className="space-y-2 border-b border-slate-200 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Inspector</p>
            {selectedNode ? (
              <div className="space-y-2 text-xs">
                <p className="font-semibold text-slate-800">{selectedNode.data.label}</p>
                <p className="text-slate-500">{selectedNode.data.nodeType ?? selectedNode.data.agent}</p>
                <div className="flex flex-wrap gap-1">
                  {(selectedNode.data.inputs ?? []).map((input) => (
                    <span key={`${input.name}-${input.artifact_type}`} className="rounded bg-sky-50 px-1.5 py-0.5 text-[11px] text-sky-700">
                      in:{input.artifact_type}
                    </span>
                  ))}
                  {(selectedNode.data.outputs ?? []).map((output) => (
                    <span key={`${output.name}-${output.artifact_type}`} className="rounded bg-emerald-50 px-1.5 py-0.5 text-[11px] text-emerald-700">
                      out:{output.artifact_type}
                    </span>
                  ))}
                </div>
                <p className="text-slate-500">Timeout: {selectedNode.data.timeout_seconds ?? "default"}s</p>
                <p className="text-slate-500">Retries: {selectedNode.data.retry_policy?.max_attempts ?? "default"}</p>
              </div>
            ) : (
              <p className="text-xs text-slate-500">Select a node to configure inputs, outputs, retries, and resources.</p>
            )}
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
          {specWarnings.length > 0 ? (
            <div className="border-t border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {specWarnings.map((warning, index) => (
                <p key={`${warning}-${index}`}>{warning}</p>
              ))}
            </div>
          ) : null}
          {specError ? <p className="border-t border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">{specError}</p> : null}
          {yamlError ? <p className="border-t border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{yamlError}</p> : null}
        </aside>
      </div>
      <div className="flex h-20 items-center justify-between border-t border-slate-200 bg-white px-4 text-xs text-slate-600" aria-live="polite">
        <div>
          <p className="font-semibold text-slate-700">Execution Drawer</p>
          <p>{nodes.length} nodes, {edges.length} edges. Test runs stream node events into Monitor and Run Detail.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="xs" disabled={!selectedNode}>
            Test Node
          </Button>
          <Button variant="secondary" size="xs" disabled={!savedId}>
            Retry Failed Node
          </Button>
        </div>
      </div>
    </div>
  );
}
