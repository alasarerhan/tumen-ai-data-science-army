import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Avatar } from "../components/ui/avatar";
import { useAuth } from "../context/AuthContext";
import { getWorkflow, publishWorkflow, type WorkflowSpec } from "../api/workflows";
import { formatRelativeTime } from "../utils/time";
import { cn } from "../lib/utils";
import {
  ArrowLeft,
  GitBranch,
  History,
  Save,
  Play,
  Pencil,
  Copy,
  ChevronRight,
  Clock,
  CheckCircle2,
  RotateCcw,
  Download,
  Upload,
  AlertCircle,
  X,
} from "lucide-react";

type WorkflowStatus = "published" | "draft" | "archived";
const statusVariant: Record<WorkflowStatus, "success" | "warning" | "neutral"> = {
  published: "success",
  draft: "warning",
  archived: "neutral",
};
const SAVE_FEEDBACK_DELAY_MS = 800;
const SAVE_RESET_DELAY_MS = 2000;

// Mock YAML specs per workflow
const YAML_SPECS: Record<string, string> = {
  wf1: `name: sales_intelligence_pipeline
version: "3.0.0"
description: "End-to-end sales data analysis with ML-powered forecasting"

triggers:
  - type: schedule
    cron: "0 6 * * 1-5"
  - type: manual

agents:
  - id: data_loader
    type: eda
    name: DataLoader
    config:
      source: "sales_db"
      query: "SELECT * FROM sales WHERE date >= :start_date"
      output: raw_sales

  - id: data_cleaner
    type: eda
    name: DataCleaner
    depends_on: [data_loader]
    config:
      input: raw_sales
      strategies:
        missing_values: median
        outliers: iqr_1.5
      output: clean_sales

  - id: eda_agent
    type: eda
    name: EDA Agent
    depends_on: [data_cleaner]
    config:
      input: clean_sales
      generate:
        - correlation_matrix
        - distribution_plots
        - trend_analysis
      output: eda_results

  - id: ml_agent
    type: ml
    name: H2O AutoML
    depends_on: [data_cleaner]
    config:
      input: clean_sales
      target: revenue_next_quarter
      max_models: 20
      max_runtime_secs: 300
      output: ml_model

  - id: hitl_gate
    type: hitl
    name: HITL Gate
    depends_on: [ml_agent]
    config:
      reviewers: ["alex@acme.com"]
      timeout_hours: 24
      auto_approve_threshold: 0.92

  - id: narrative_agent
    type: strategic
    name: NarrativeAgent
    depends_on: [hitl_gate, eda_agent]
    config:
      template: executive_summary
      audience: c_suite
      output: final_report

outputs:
  - id: final_report
    format: HTML
    destination: s3://insights-bucket/reports/

retry:
  max_attempts: 3
  backoff: exponential
`,
  wf2: `name: customer_churn_ml
version: "5.0.0"
description: "Predicts customer churn using H2O AutoML"

triggers:
  - type: schedule
    cron: "0 8 * * 1"

agents:
  - id: data_loader
    type: eda
    name: DataLoader
    config:
      source: "crm_db"
      output: raw_customers

  - id: feature_engineer
    type: eda
    name: DataCleaner
    depends_on: [data_loader]
    config:
      input: raw_customers
      features:
        - tenure_months
        - avg_monthly_spend
        - support_tickets_90d
        - login_frequency
      output: feature_matrix

  - id: churn_model
    type: ml
    name: H2O AutoML
    depends_on: [feature_engineer]
    config:
      input: feature_matrix
      target: churned
      output: churn_predictions

  - id: shap_explainer
    type: ml
    name: SHAP Explainer
    depends_on: [churn_model]
    config:
      model: churn_model
      output: shap_values

outputs:
  - id: churn_predictions
    format: CSV
`,
  default: `name: workflow
version: "1.0.0"
description: "AI agent workflow"

triggers:
  - type: manual

agents:
  - id: agent_1
    type: eda
    name: DataLoader
    config:
      source: "default"
      output: data

outputs:
  - id: data
    format: JSON
`,
};

// Mock version history
const VERSION_HISTORY = [
  { version: "v3", authorName: "AI System", timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), message: "Add HITL gate with auto-approve threshold", isCurrent: true },
  { version: "v2", authorName: "AI System", timestamp: new Date(Date.now() - 1000 * 60 * 60 * 48), message: "Tune H2O AutoML max runtime to 300s", isCurrent: false },
  { version: "v1", authorName: "AI System", timestamp: new Date(Date.now() - 1000 * 60 * 60 * 120), message: "Initial workflow definition", isCurrent: false },
];

export default function WorkflowDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [workflow, setWorkflow] = useState<WorkflowSpec | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!id || !workspaceId) return;
    let cancelled = false;
    setLoadError(null);
    getWorkflow(id, workspaceId)
      .then((result) => {
        if (!cancelled) setWorkflow(result);
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : "Failed to load workflow");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, workspaceId]);

  const yamlContent = YAML_SPECS[id ?? "default"] ?? YAML_SPECS.default;

  const [activeTab, setActiveTab] = useState<"spec" | "history">("spec");
  const [editorValue, setEditorValue] = useState(yamlContent);
  const [isDirty, setIsDirty] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [showRestoreConfirm, setShowRestoreConfirm] = useState<string | null>(null);

  if (!workflow) {
    return (
      <AppShell>
        <div className="p-6 flex flex-col items-center justify-center h-full text-slate-500">
          <AlertCircle size={40} className="mb-3 text-slate-300" />
          <p className="text-sm">{loadError ?? "Workflow not found."}</p>
          <button
            className="mt-4 text-sm text-indigo-600 hover:underline"
            onClick={() => navigate("/workflows")}
          >
            Back to Workflows
          </button>
        </div>
      </AppShell>
    );
  }

  const handleEditorChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setEditorValue(e.target.value);
    setIsDirty(true);
    setSaveState("idle");
  };

  const handleSave = () => {
    setSaveState("saving");
    setTimeout(() => {
      setSaveState("saved");
      setIsDirty(false);
      setTimeout(() => setSaveState("idle"), SAVE_RESET_DELAY_MS);
    }, SAVE_FEEDBACK_DELAY_MS);
  };

  const handleRestoreConfirmed = () => {
    setShowRestoreConfirm(null);
    setEditorValue(yamlContent);
    setIsDirty(false);
    setSaveState("idle");
  };

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/workflows")}
              className="p-1.5 rounded-[6px] text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="Back to workflows"
            >
              <ArrowLeft size={16} />
            </button>
            <div className="flex items-center gap-2">
              <div className="size-7 rounded-[6px] bg-indigo-50 dark:bg-indigo-900/30 flex items-center justify-center">
                <GitBranch size={14} className="text-indigo-600 dark:text-indigo-400" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-sm font-semibold text-slate-900 dark:text-slate-50">{workflow.name}</h1>
                  <Badge variant={statusVariant[workflow.status]} size="sm">
                    {workflow.status.charAt(0).toUpperCase() + workflow.status.slice(1)}
                  </Badge>
                  {isDirty && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 font-medium">
                      Unsaved
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-400 font-mono">{workflow.version}</p>
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
            <Button
              variant="secondary"
              size="sm"
              leadingIcon={<Play size={13} />}
            >
              Run
            </Button>
            <Button
              variant="primary"
              size="sm"
              leadingIcon={
                saveState === "saving"
                  ? <div className="size-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                  : saveState === "saved"
                  ? <CheckCircle2 size={13} />
                  : <Save size={13} />
              }
              onClick={handleSave}
              disabled={!isDirty || saveState === "saving"}
            >
              {saveState === "saving" ? "Saving..." : saveState === "saved" ? "Saved" : "Save"}
            </Button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex-shrink-0 px-6">
          {[
            { key: "spec", label: "Spec Editor", icon: <GitBranch size={13} /> },
            { key: "history", label: "Version History", icon: <History size={13} /> },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as "spec" | "history")}
              className={cn(
                "flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium border-b-2 -mb-px transition-colors",
                activeTab === tab.key
                  ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                  : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              )}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {activeTab === "spec" ? (
            <div className="flex h-full">
              {/* YAML Editor */}
              <div className="flex-1 flex flex-col overflow-hidden">
                {/* Editor toolbar */}
                <div className="flex items-center justify-between px-4 py-2 bg-slate-800 dark:bg-slate-950 border-b border-slate-700 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-400">workflow.yaml</span>
                    <span className="text-[10px] px-1.5 py-0.5 bg-slate-700 rounded text-slate-300 font-mono">YAML</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
                      onClick={() => navigator.clipboard?.writeText(editorValue)}
                    >
                      <Copy size={11} />
                      Copy
                    </button>
                    <button
                      className="text-[11px] text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
                    >
                      <Download size={11} />
                      Export
                    </button>
                  </div>
                </div>

                {/* Line numbers + editor */}
                <div className="flex flex-1 overflow-hidden bg-slate-900 dark:bg-slate-950 font-mono">
                  {/* Line numbers */}
                  <div
                    className="select-none text-right pr-4 pl-4 pt-4 text-[12px] leading-[1.6] text-slate-600 border-r border-slate-700 flex-shrink-0 overflow-hidden"
                    style={{ minWidth: "48px" }}
                  >
                    {editorValue.split("\n").map((_, i) => (
                      <div key={i}>{i + 1}</div>
                    ))}
                  </div>

                  {/* Textarea */}
                  <textarea
                    value={editorValue}
                    onChange={handleEditorChange}
                    spellCheck={false}
                    className="flex-1 resize-none bg-transparent text-slate-200 text-[12px] leading-[1.6] px-4 pt-4 pb-4 focus:outline-none font-mono overflow-auto"
                    style={{ tabSize: 2 }}
                  />
                </div>
              </div>

              {/* Right panel: Schema hints + metadata */}
              <div className="w-64 border-l border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex flex-col overflow-hidden flex-shrink-0">
                {/* Workflow metadata */}
                <div className="p-4 border-b border-slate-100 dark:border-slate-800">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-3">Metadata</p>
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Author</span>
                      <span className="text-slate-700 dark:text-slate-300">--</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Modified</span>
                      <span className="text-slate-700 dark:text-slate-300">{workflow.updated_at ? formatRelativeTime(workflow.updated_at) : "--"}</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Nodes</span>
                      <span className="text-slate-700 dark:text-slate-300">--</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-500">Edges</span>
                      <span className="text-slate-700 dark:text-slate-300">--</span>
                    </div>
                  </div>
                </div>

                {/* Schema reference */}
                <div className="p-4 flex-1 overflow-y-auto">
                  <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-3">Schema Reference</p>
                  <div className="space-y-3">
                    {[
                      { key: "name", type: "string", required: true, desc: "Unique workflow identifier" },
                      { key: "version", type: "semver", required: true, desc: "Semantic version" },
                      { key: "description", type: "string", required: false, desc: "Human-readable description" },
                      { key: "triggers", type: "list", required: true, desc: "schedule, manual, or webhook" },
                      { key: "agents", type: "list", required: true, desc: "Ordered agent definitions" },
                      { key: "outputs", type: "list", required: false, desc: "Output artifacts" },
                      { key: "retry", type: "object", required: false, desc: "Retry configuration" },
                    ].map((field) => (
                      <div key={field.key} className="text-[11px] space-y-0.5">
                        <div className="flex items-center gap-1.5">
                          <code className="text-indigo-600 dark:text-indigo-400 font-mono">{field.key}</code>
                          <span className="text-slate-400 font-mono">{field.type}</span>
                          {field.required && (
                            <span className="text-[9px] px-1 py-px bg-red-50 dark:bg-red-900/20 text-red-500 rounded">required</span>
                          )}
                        </div>
                        <p className="text-slate-500 leading-relaxed">{field.desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Actions */}
                <div className="p-4 border-t border-slate-100 dark:border-slate-800 space-y-2">
                  <button className="w-full flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                    <Upload size={12} />
                    Import from file
                  </button>
                  <button className="w-full flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400 transition-colors">
                    <Download size={12} />
                    Export as YAML
                  </button>
                </div>
              </div>
            </div>
          ) : (
            /* Version History Panel */
            <div className="h-full overflow-y-auto bg-white dark:bg-slate-900">
              <div className="max-w-2xl mx-auto p-6">
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-1">Version History</h2>
                <p className="text-xs text-slate-500 mb-6">All saved versions of this workflow spec.</p>

                <div className="relative">
                  {/* Timeline line */}
                  <div className="absolute left-[15px] top-4 bottom-4 w-px bg-slate-200 dark:bg-slate-700" />

                  <div className="space-y-4">
                    {VERSION_HISTORY.map((v, idx) => (
                      <div key={v.version} className="flex gap-4 items-start">
                        {/* Timeline dot */}
                        <div className={cn(
                          "relative z-10 size-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                          v.isCurrent
                            ? "bg-indigo-600 text-white"
                            : "bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 text-slate-400"
                        )}>
                          {v.isCurrent ? <CheckCircle2 size={14} /> : <Clock size={12} />}
                        </div>

                        {/* Card */}
                        <div className={cn(
                          "flex-1 rounded-[8px] border p-4 transition-shadow",
                          v.isCurrent
                            ? "border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-900/10"
                            : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:shadow-sm"
                        )}>
                          <div className="flex items-start justify-between mb-2">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-semibold text-slate-900 dark:text-slate-50 font-mono">{v.version}</span>
                              {v.isCurrent && (
                                <span className="text-[10px] px-1.5 py-0.5 bg-indigo-600 text-white rounded font-medium">Current</span>
                              )}
                            </div>
                            <div className="flex items-center gap-1">
                              {!v.isCurrent && (
                                <button
                                  onClick={() => setShowRestoreConfirm(v.version)}
                                  className="flex items-center gap-1 text-xs text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 px-2 py-1 rounded hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors"
                                >
                                  <RotateCcw size={11} />
                                  Restore
                                </button>
                              )}
                              <button
                                className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700 px-2 py-1 rounded hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                              >
                                <Copy size={11} />
                                Copy
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-slate-600 dark:text-slate-400 mb-3">
                            {v.message}
                          </p>
                          <div className="flex items-center gap-2">
                            <div className="size-[18px] rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-[9px] font-semibold text-slate-500">AI</div>
                            <span className="text-xs text-slate-500">{v.authorName}</span>
                            <span className="text-slate-300 dark:text-slate-600">·</span>
                            <span className="text-xs text-slate-400">{formatRelativeTime(v.timestamp)}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Restore confirmation modal */}
      {showRestoreConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setShowRestoreConfirm(null)} />
          <div className="relative bg-white dark:bg-slate-900 rounded-[12px] shadow-xl w-full max-w-sm mx-4 p-6">
            <button
              onClick={() => setShowRestoreConfirm(null)}
              className="absolute top-4 right-4 p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <X size={14} />
            </button>
            <div className="flex items-center gap-3 mb-4">
              <div className="size-9 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                <RotateCcw size={16} className="text-amber-600" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-50">Restore version {showRestoreConfirm}?</h3>
                <p className="text-xs text-slate-500">This will overwrite your current spec.</p>
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setShowRestoreConfirm(null)}>Cancel</Button>
              <Button variant="primary" size="sm" onClick={handleRestoreConfirmed}>
                Restore
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}


