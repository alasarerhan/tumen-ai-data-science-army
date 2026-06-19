import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  FileText,
  GitBranch,
  History,
  Pencil,
  Play,
} from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";
import { getWorkflow, getWorkflowVersions, type WorkflowSpec, type WorkflowVersionEntry } from "../api/workflows";
import { formatRelativeTime } from "../utils/time";
import { cn } from "../lib/utils";

type WorkflowStatus = WorkflowSpec["status"];

const statusVariant: Record<WorkflowStatus, "success" | "warning" | "neutral"> = {
  published: "success",
  draft: "warning",
  archived: "neutral",
};

function serializeWorkflowSpec(workflow: WorkflowSpec): string {
  return JSON.stringify(
    {
      id: workflow.id,
      name: workflow.name,
      version: workflow.version,
      status: workflow.status,
      spec: workflow.spec,
      validation_summary: workflow.validation_summary,
    },
    null,
    2,
  );
}

function countWorkflowNodes(workflowSpec: Record<string, unknown>): number {
  const graph = workflowSpec.graph as { nodes?: unknown[] } | undefined;
  if (Array.isArray(graph?.nodes)) return graph.nodes.length;
  return Array.isArray(workflowSpec.steps) ? workflowSpec.steps.length : 0;
}

function countWorkflowEdges(workflowSpec: Record<string, unknown>): number {
  const graph = workflowSpec.graph as { edges?: unknown[] } | undefined;
  if (Array.isArray(graph?.edges)) return graph.edges.length;
  const steps = Array.isArray(workflowSpec.steps) ? workflowSpec.steps : [];
  return steps.reduce((count, step) => count + (((step as { depends_on?: unknown[] }).depends_on?.length) ?? 0), 0);
}

export default function WorkflowDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [workflow, setWorkflow] = useState<WorkflowSpec | null>(null);
  const [versions, setVersions] = useState<WorkflowVersionEntry[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"spec" | "history">("spec");

  useEffect(() => {
    if (!id || !workspaceId) return;
    let cancelled = false;
    setLoadError(null);
    Promise.all([
      getWorkflow(id, workspaceId),
      getWorkflowVersions(id, workspaceId).catch(() => ({ versions: [] })),
    ])
      .then(([workflowResult, versionResult]) => {
        if (cancelled) return;
        setWorkflow(workflowResult);
        setVersions(versionResult.versions ?? []);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load workflow");
          setWorkflow(null);
          setVersions([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, workspaceId]);

  const editorValue = useMemo(() => (workflow ? serializeWorkflowSpec(workflow) : ""), [workflow]);

  if (!workflow) {
    return (
      <AppShell>
        <div className="flex h-full flex-col items-center justify-center p-6 text-slate-500">
          <AlertCircle size={40} className="mb-3 text-slate-300" />
          <p className="text-sm">{loadError ?? "Workflow not found."}</p>
          <button className="mt-4 text-sm text-indigo-600 hover:underline" onClick={() => navigate("/workflows")}>
            Back to Workflows
          </button>
        </div>
      </AppShell>
    );
  }

  const workflowSpec = workflow.spec as Record<string, unknown>;
  const nodeCount = countWorkflowNodes(workflowSpec);
  const edgeCount = countWorkflowEdges(workflowSpec);
  const validation = workflow.validation_summary;
  const validationVariant =
    validation.status === "safe" ? "success" : validation.status === "invalid" ? "danger" : "warning";
  const validationTitle =
    validation.status === "safe" ? "Chain Safe" : validation.status === "invalid" ? "Invalid Chain" : "Advisory Chain";

  return (
    <AppShell>
      <div className="flex h-full flex-col overflow-hidden">
        <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-700 dark:bg-slate-900">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/workflows")}
              className="rounded-[6px] p-1.5 text-slate-500 transition-colors hover:bg-slate-100 dark:hover:bg-slate-800"
              aria-label="Back to workflows"
            >
              <ArrowLeft size={16} />
            </button>
            <div className="flex items-center gap-2">
              <div className="flex size-7 items-center justify-center rounded-[6px] bg-indigo-50 dark:bg-indigo-900/30">
                <GitBranch size={14} className="text-indigo-600 dark:text-indigo-400" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{workflow.name}</h1>
                  <Badge variant={statusVariant[workflow.status]} size="sm">
                    {workflow.status.charAt(0).toUpperCase() + workflow.status.slice(1)}
                  </Badge>
                  <Badge variant={validationVariant} size="sm">
                    {validationTitle}
                  </Badge>
                </div>
                <p className="font-mono text-xs text-slate-400">v{workflow.version}</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={<Pencil size={13} />}
              onClick={() => navigate(`/workflows/${id}/designer`)}
            >
              Open Designer
            </Button>
            <Button variant="secondary" size="sm" leadingIcon={<Play size={13} />} disabled={validation.status === "invalid"}>
              Run
            </Button>
            <Button variant="secondary" size="sm" leadingIcon={<FileText size={13} />} disabled title="Versioned spec edits require a dedicated update API.">
              Read-only
            </Button>
          </div>
        </div>

        <div className="flex flex-shrink-0 border-b border-slate-200 bg-white px-6 dark:border-slate-700 dark:bg-slate-900">
          {[
            { key: "spec", label: "Spec", icon: <GitBranch size={13} /> },
            { key: "history", label: "Version History", icon: <History size={13} /> },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as "spec" | "history")}
              className={cn(
                "-mb-px flex items-center gap-1.5 border-b-2 px-4 py-2.5 text-xs font-medium transition-colors",
                activeTab === tab.key
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300",
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === "spec" ? (
            <div className="flex h-full">
              <div className="flex flex-1 flex-col overflow-hidden">
                <div className="flex flex-shrink-0 items-center justify-between border-b border-slate-700 bg-slate-800 px-4 py-2 dark:bg-slate-950">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-[10px] text-slate-400">workflow.spec.json</span>
                    <span className="rounded bg-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">JSON</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="flex items-center gap-1 text-[11px] text-slate-400 transition-colors hover:text-slate-200"
                      onClick={() => navigator.clipboard?.writeText(editorValue)}
                      aria-label="Copy workflow spec JSON"
                    >
                      <Copy size={11} />
                      Copy
                    </button>
                    <button
                      className="flex items-center gap-1 text-[11px] text-slate-400 transition-colors hover:text-slate-200"
                      onClick={() => navigator.clipboard?.writeText(editorValue)}
                      aria-label="Export workflow spec JSON"
                    >
                      <Download size={11} />
                      Export
                    </button>
                  </div>
                </div>

                <div className="flex flex-1 overflow-hidden bg-slate-900 font-mono dark:bg-slate-950">
                  <div className="min-w-12 flex-shrink-0 select-none overflow-hidden border-r border-slate-700 px-4 pt-4 text-right text-[12px] leading-[1.6] text-slate-600">
                    {editorValue.split("\n").map((_, index) => (
                      <div key={index}>{index + 1}</div>
                    ))}
                  </div>
                  <textarea
                    value={editorValue}
                    readOnly
                    spellCheck={false}
                    aria-label="Workflow spec JSON"
                    className="flex-1 resize-none overflow-auto bg-transparent px-4 pb-4 pt-4 font-mono text-[12px] leading-[1.6] text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    style={{ tabSize: 2 }}
                  />
                </div>
              </div>

              <div className="flex w-72 flex-shrink-0 flex-col overflow-hidden border-l border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900">
                <div className="border-b border-slate-100 p-4 dark:border-slate-800">
                  <p className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Metadata</p>
                  <div className="space-y-2">
                    {[
                      ["Modified", workflow.updated_at ? formatRelativeTime(workflow.updated_at) : "--"],
                      ["Nodes", String(nodeCount)],
                      ["Edges", String(edgeCount)],
                      ["Chain", validationTitle],
                      ["Created", workflow.created_at ? formatRelativeTime(workflow.created_at) : "--"],
                    ].map(([label, value]) => (
                      <div key={label} className="flex justify-between gap-3 text-xs">
                        <span className="text-slate-500">{label}</span>
                        <span className="text-right text-slate-700 dark:text-slate-300">{value}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {(validation.errors.length > 0 || validation.warnings.length > 0) && (
                  <div className="border-b border-slate-100 p-4 dark:border-slate-800">
                    <p className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Validation</p>
                    <div className="space-y-2">
                      {validation.errors.map((message) => (
                        <p key={message} className="rounded bg-red-50 px-2 py-1 text-[11px] text-red-700 dark:bg-red-950/30 dark:text-red-300">
                          {message}
                        </p>
                      ))}
                      {validation.warnings.map((message) => (
                        <p key={message} className="rounded bg-amber-50 px-2 py-1 text-[11px] text-amber-700 dark:bg-amber-950/30 dark:text-amber-300">
                          {message}
                        </p>
                      ))}
                    </div>
                  </div>
                )}

                <div className="flex-1 overflow-y-auto p-4">
                  <p className="mb-3 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Spec Contract</p>
                  <div className="space-y-3">
                    {[
                      ["name", "Workflow display name and version grouping key"],
                      ["status", "draft, published, or archived"],
                      ["spec", "Persisted workflow graph or step document from API"],
                      ["validation_summary", "Backend chain validation status and messages"],
                    ].map(([field, description]) => (
                      <div key={field} className="space-y-0.5 text-[11px]">
                        <code className="font-mono text-indigo-600 dark:text-indigo-400">{field}</code>
                        <p className="leading-relaxed text-slate-500">{description}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full overflow-y-auto bg-white dark:bg-slate-900">
              <div className="mx-auto max-w-2xl p-6">
                <h2 className="mb-1 text-sm font-semibold text-slate-800 dark:text-slate-200">Version History</h2>
                <p className="mb-6 text-xs text-slate-500">
                  Real version records from the versioning API. Restore and diff remain disabled until the backend contract is complete.
                </p>

                {versions.length === 0 ? (
                  <div className="rounded-[8px] border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    No version history records yet. Current workflow spec v{workflow.version} is loaded from the workflow API.
                  </div>
                ) : (
                  <div className="relative">
                    <div className="absolute bottom-4 left-[15px] top-4 w-px bg-slate-200 dark:bg-slate-700" />
                    <div className="space-y-4">
                      {versions.map((version) => (
                        <div key={version.id} className="flex items-start gap-4">
                          <div
                            className={cn(
                              "relative z-10 mt-0.5 flex size-8 flex-shrink-0 items-center justify-center rounded-full",
                              version.version === workflow.version
                                ? "bg-indigo-600 text-white"
                                : "border-2 border-slate-200 bg-white text-slate-400 dark:border-slate-700 dark:bg-slate-800",
                            )}
                          >
                            {version.version === workflow.version ? <CheckCircle2 size={14} /> : <Clock size={12} />}
                          </div>
                          <div
                            className={cn(
                              "flex-1 rounded-[8px] border p-4",
                              version.version === workflow.version
                                ? "border-indigo-200 bg-indigo-50 dark:border-indigo-800 dark:bg-indigo-900/10"
                                : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900",
                            )}
                          >
                            <div className="mb-2 flex items-start justify-between gap-3">
                              <div className="flex items-center gap-2">
                                <span className="font-mono text-sm font-semibold text-slate-900 dark:text-slate-50">v{version.version}</span>
                                {version.version === workflow.version ? (
                                  <span className="rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-medium text-white">Current</span>
                                ) : null}
                              </div>
                              <Button variant="ghost" size="xs" disabled title="Restore requires a version restore API.">
                                Restore
                              </Button>
                            </div>
                            <p className="mb-3 text-xs text-slate-600 dark:text-slate-400">
                              {version.changelog || "No changelog recorded."}
                            </p>
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                              <span>{version.created_by || "unknown"}</span>
                              <span className="text-slate-300 dark:text-slate-600">.</span>
                              <span>{version.created_at ? formatRelativeTime(version.created_at) : "--"}</span>
                              <span className="text-slate-300 dark:text-slate-600">.</span>
                              <span>{version.status}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
