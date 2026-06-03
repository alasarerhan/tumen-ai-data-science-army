import { useMemo, useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";
import { formatRelativeTime } from "../utils/time";
import { cn } from "../lib/utils";
import {
  useCreateDataSource,
  useDataSources,
  useDeleteDataSource,
  useTestDataSource,
} from "../hooks/useDataSources";
import {
  Plus,
  Database,
  FileText,
  Plug,
  MoreHorizontal,
  Edit,
  Copy,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  X,
} from "lucide-react";

const healthConfig = {
  healthy: { icon: <CheckCircle2 size={12} />, color: "text-emerald-500", label: "Healthy" },
  degraded: { icon: <AlertTriangle size={12} />, color: "text-amber-500", label: "Pending" },
  error: { icon: <AlertCircle size={12} />, color: "text-red-500", label: "Error" },
};

type DataSourceHealthKey = keyof typeof healthConfig;

const typeIcon = {
  "Local File": <FileText size={18} className="text-emerald-600" />,
  "SQL": <Database size={18} className="text-sky-600" />,
  "MCP Plugin": <Plug size={18} className="text-violet-600" />,
};

const typeBg = {
  "Local File": "bg-emerald-50 dark:bg-emerald-900/20",
  "SQL": "bg-sky-50 dark:bg-sky-900/20",
  "MCP Plugin": "bg-violet-50 dark:bg-violet-900/20",
};

const WIZARD_TYPES = [
  {
    id: "file",
    label: "Local File",
    icon: <FileText size={20} />,
    desc: "CSV, Excel, Parquet, JSON files from local storage.",
    color: "text-emerald-600 bg-emerald-50",
  },
  {
    id: "sql",
    label: "SQL Database",
    icon: <Database size={20} />,
    desc: "PostgreSQL, MySQL, SQLite, DuckDB via connection URI.",
    color: "text-sky-600 bg-sky-50",
  },
  {
    id: "mcp",
    label: "MCP Plugin",
    icon: <Plug size={20} />,
    desc: "Custom connector via Model Context Protocol.",
    color: "text-violet-600 bg-violet-50",
  },
];

function getKindLabel(kind: string) {
  if (kind === "file") return "Local File";
  if (kind === "mcp") return "MCP Plugin";
  return "SQL";
}

function normalizeConnectionUri(kind: string, value: string) {
  const trimmed = value.trim();
  if (kind === "file") {
    if (trimmed.startsWith("file:///")) return trimmed;
    const normalizedPath = trimmed.replace(/\\/g, "/").replace(/^\/+/, "");
    return `file:///${normalizedPath}`;
  }
  if (kind === "mcp") {
    if (trimmed.startsWith("mcp://")) return trimmed;
    return `mcp://${trimmed.replace(/^\/+/, "")}`;
  }
  return trimmed;
}

function extractConnectionHealth(metadata: Record<string, unknown>) {
  const test = metadata.connection_test as
    | { status?: string; message?: string; checked_at?: string }
    | undefined;
  const status: DataSourceHealthKey =
    test?.status === "ok" ? "healthy" : test?.status === "error" ? "error" : "degraded";
  return {
    status,
    message: test?.message ?? "Connection has not been tested yet.",
    checkedAt: test?.checked_at ?? null,
  };
}

export default function DataSources() {
  const { workspaceId } = useAuth();
  const [pageError, setPageError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formUri, setFormUri] = useState("");
  const [testingId, setTestingId] = useState<string | null>(null);
  const [wizardTesting, setWizardTesting] = useState(false);
  const [wizardTestResult, setWizardTestResult] = useState<{ status: "ok" | "error"; message: string } | null>(null);

  const dataSourcesQuery = useDataSources(workspaceId);
  const createDataSourceMutation = useCreateDataSource(workspaceId);
  const deleteDataSourceMutation = useDeleteDataSource(workspaceId);
  const testDataSourceMutation = useTestDataSource(workspaceId);

  const dataSources = dataSourcesQuery.data?.items ?? [];
  const loadingDs = dataSourcesQuery.isLoading;
  const effectiveError = useMemo(() => {
    if (pageError) return pageError;
    if (!dataSourcesQuery.error) return null;
    return dataSourcesQuery.error instanceof Error
      ? dataSourcesQuery.error.message
      : "Failed to load data sources";
  }, [dataSourcesQuery.error, pageError]);

  const reviewConnection = selectedType ? normalizeConnectionUri(selectedType, formUri) : formUri;
  const canContinueFromStep1 = Boolean(selectedType);
  const canTestConnection = Boolean(formName.trim() && formUri.trim() && selectedType);

  const stepTitle =
    selectedType === "file" ? "Local Path" : selectedType === "mcp" ? "Plugin Module" : "Connection URI";
  const stepPlaceholder =
    selectedType === "file"
      ? "C:\\data\\exports or /data/warehouse"
      : selectedType === "mcp"
        ? "my_package.connectors.custom_source"
        : "postgresql://user:pass@host/db";

  const reviewRows = [
    ["Type", WIZARD_TYPES.find((t) => t.id === selectedType)?.label || ""],
    ["Name", formName || "--"],
    ["Connection", reviewConnection || "--"],
    ["Status", wizardTestResult?.status === "ok" ? "Validated" : "Needs attention"],
  ];

  const resetWizard = () => {
    setShowModal(false);
    setWizardStep(1);
    setSelectedType(null);
    setFormName("");
    setFormUri("");
    setWizardTesting(false);
    setWizardTestResult(null);
  };

  const handleDelete = async (id: string) => {
    if (!workspaceId) return;
    try {
      await deleteDataSourceMutation.mutateAsync(id);
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : "Failed to delete data source");
    }
  };

  const handleTest = async (id: string) => {
    if (!workspaceId) return;
    setTestingId(id);
    setPageError(null);
    try {
      const result = await testDataSourceMutation.mutateAsync(id);
      setWizardTestResult({
        status: result.status === "ok" ? "ok" : "error",
        message: result.message,
      });
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setTestingId(null);
    }
  };

  const handleWizardTest = async () => {
    if (!workspaceId || !selectedType || !formName.trim() || !formUri.trim()) return;
    setWizardTesting(true);
    setPageError(null);
    setWizardTestResult(null);
    try {
      const created = await createDataSourceMutation.mutateAsync({
        workspace_id: workspaceId,
        name: formName.trim(),
        kind: selectedType,
        connection_uri: normalizeConnectionUri(selectedType, formUri),
      });
      const result = await testDataSourceMutation.mutateAsync(created.id);
      setWizardTestResult({
        status: result.status === "ok" ? "ok" : "error",
        message: result.message,
      });
      setWizardStep(3);
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : "Failed to test data source");
    } finally {
      setWizardTesting(false);
    }
  };

  const handleSave = async () => {
    if (!wizardTestResult || wizardTestResult.status !== "ok") {
      setPageError("Run a successful connection test before saving.");
      return;
    }
    setPageError(null);
    resetWizard();
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-[1280px] space-y-5 p-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
              Data Sources
            </h1>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Connect your data to enable AI-powered analysis.
            </p>
          </div>
          <Button variant="primary" size="md" leadingIcon={<Plus size={14} />} onClick={() => setShowModal(true)}>
            Add Data Source
          </Button>
        </div>

        {effectiveError ? (
          <div className="rounded-[8px] border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {effectiveError}
          </div>
        ) : null}

        <div className="overflow-hidden rounded-[8px] border border-slate-200 bg-white shadow-sm divide-y divide-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:divide-slate-800">
          {loadingDs ? <p className="py-12 text-center text-sm text-slate-400">Loading data sources...</p> : null}
          {!loadingDs && dataSources.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-400">No data sources connected yet.</p>
          ) : null}
          {dataSources.map((ds) => {
            const kindLabel = getKindLabel(ds.kind);
            const health = extractConnectionHealth(ds.metadata);
            const healthUi = healthConfig[health.status];
            return (
              <div key={ds.id} className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50">
                <div className={cn("size-10 rounded-[8px] flex items-center justify-center flex-shrink-0", typeBg[kindLabel as keyof typeof typeBg] ?? "bg-slate-50")}>
                  {typeIcon[kindLabel as keyof typeof typeIcon] ?? <Database size={18} className="text-slate-500" />}
                </div>

                <div className="w-48 flex-shrink-0">
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{ds.name}</p>
                  <Badge variant={ds.kind === "sql" ? "info" : ds.kind === "mcp" ? "violet" : "success"} size="sm">
                    {kindLabel}
                  </Badge>
                </div>

                <div className="min-w-0 flex-1">
                  <code className="block truncate text-xs font-mono text-slate-500 dark:text-slate-400">
                    {ds.connection_uri || "--"}
                  </code>
                  <div className={cn("mt-0.5 flex items-center gap-1", healthUi.color)}>
                    {healthUi.icon}
                    <span className="text-xs">{healthUi.label}</span>
                    <span className="text-[10px] text-slate-400">{health.message}</span>
                  </div>
                </div>

                <div className="flex flex-shrink-0 items-center gap-3">
                  <span className="text-xs text-slate-400">
                    {health.checkedAt ? `Checked ${formatRelativeTime(health.checkedAt)}` : `Added ${formatRelativeTime(ds.created_at)}`}
                  </span>
                  <Button variant="ghost" size="xs" loading={testingId === ds.id} onClick={() => handleTest(ds.id)}>
                    Test Connection
                  </Button>
                  <div className="relative">
                    <button
                      onClick={() => setOpenMenu(openMenu === ds.id ? null : ds.id)}
                      className="rounded p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                      aria-label={`${ds.name} actions`}
                    >
                      <MoreHorizontal size={15} />
                    </button>
                    {openMenu === ds.id ? (
                      <div className="absolute right-0 top-full z-20 mt-1 w-36 rounded-[8px] border border-slate-200 bg-white py-1 shadow-md dark:border-slate-700 dark:bg-slate-800">
                        {[
                          { label: "Edit", icon: <Edit size={13} /> },
                          { label: "Duplicate", icon: <Copy size={13} /> },
                          { label: "Delete", icon: <Trash2 size={13} />, danger: true, action: () => handleDelete(ds.id) },
                        ].map((item) => (
                          <button
                            key={item.label}
                            onClick={() => {
                              item.action?.();
                              setOpenMenu(null);
                            }}
                            className={cn(
                              "flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700",
                              item.danger ? "text-red-600" : "text-slate-700 dark:text-slate-200",
                            )}
                          >
                            {item.icon}
                            {item.label}
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {showModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={resetWizard} />
          <div className="relative mx-4 w-full max-w-[560px] rounded-[12px] bg-white shadow-xl dark:bg-slate-900" role="dialog" aria-modal="true" aria-label="Add Data Source">
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">Add Data Source</h2>
              <button onClick={resetWizard} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close">
                <X size={16} />
              </button>
            </div>

            <div className="px-6 py-5">
              {wizardStep === 1 ? (
                <div className="space-y-3">
                  <p className="mb-4 text-sm text-slate-600 dark:text-slate-400">Choose your data source type:</p>
                  {WIZARD_TYPES.map((type) => (
                    <button
                      key={type.id}
                      onClick={() => setSelectedType(type.id)}
                      className={cn(
                        "w-full rounded-[8px] border-2 p-4 text-left transition-all flex items-start gap-4",
                        selectedType === type.id
                          ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20"
                          : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600",
                      )}
                    >
                      <div className={cn("size-10 rounded-[8px] flex items-center justify-center flex-shrink-0", type.color.split(" ")[1])}>
                        <span className={type.color.split(" ")[0]}>{type.icon}</span>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{type.label}</p>
                          {selectedType === type.id ? <CheckCircle2 size={16} className="text-indigo-600" /> : null}
                        </div>
                        <p className="mt-0.5 text-xs text-slate-500">{type.desc}</p>
                      </div>
                    </button>
                  ))}
                </div>
              ) : null}

              {wizardStep === 2 && selectedType ? (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Display Name</label>
                    <input
                      className="h-9 w-full rounded-[6px] border border-slate-200 bg-white px-3 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                      placeholder="My Data Source"
                      value={formName}
                      onChange={(e) => setFormName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">{stepTitle}</label>
                    <input
                      type={selectedType === "sql" ? "password" : "text"}
                      autoComplete="off"
                      spellCheck={false}
                      className="h-9 w-full rounded-[6px] border border-slate-200 bg-white px-3 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
                      placeholder={stepPlaceholder}
                      value={formUri}
                      onChange={(e) => setFormUri(e.target.value)}
                    />
                    <p className="text-[10px] text-slate-400">
                      {selectedType === "file"
                        ? "Absolute path will be normalized to file:/// URI format."
                        : selectedType === "mcp"
                          ? "Module names will be normalized to mcp://module.path."
                          : "Use a database URI such as postgresql://user:pass@host/db or sqlite:///C:/data/app.db."}
                    </p>
                  </div>
                </div>
              ) : null}

              {wizardStep === 3 ? (
                <div className="space-y-4">
                  <div className="space-y-2 rounded-[8px] bg-slate-50 p-4 text-sm dark:bg-slate-800">
                    <p className="mb-3 font-medium text-slate-800 dark:text-slate-200">Review & Save</p>
                    {reviewRows.map(([label, value]) => (
                      <div key={label} className="flex gap-3">
                        <span className="w-20 text-slate-400">{label}</span>
                        <span className="break-all text-slate-700 dark:text-slate-300">{value}</span>
                      </div>
                    ))}
                  </div>
                  <div
                    className={cn(
                      "flex items-center gap-2 rounded-[6px] border p-3",
                      wizardTestResult?.status === "ok"
                        ? "border-emerald-200 bg-emerald-50 dark:border-emerald-700 dark:bg-emerald-900/20"
                        : "border-red-200 bg-red-50 dark:border-red-700 dark:bg-red-900/20",
                    )}
                  >
                    {wizardTestResult?.status === "ok" ? <CheckCircle2 size={14} className="text-emerald-600" /> : <AlertCircle size={14} className="text-red-600" />}
                    <span className={cn("text-xs", wizardTestResult?.status === "ok" ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400")}>
                      {wizardTestResult?.message ?? "Connection test is required before saving."}
                    </span>
                  </div>
                </div>
              ) : null}
            </div>

            <div className="flex justify-between border-t border-slate-200 px-6 py-4 dark:border-slate-700">
              <Button variant="ghost" size="md" onClick={() => (wizardStep > 1 ? setWizardStep(wizardStep - 1) : resetWizard())}>
                {wizardStep > 1 ? "Back" : "Cancel"}
              </Button>
              <Button
                variant="primary"
                size="md"
                disabled={(wizardStep === 1 && !canContinueFromStep1) || (wizardStep === 2 && !canTestConnection)}
                onClick={() => {
                  if (wizardStep === 1) {
                    setWizardStep(2);
                    return;
                  }
                  if (wizardStep === 2) {
                    void handleWizardTest();
                    return;
                  }
                  void handleSave();
                }}
                loading={wizardTesting || createDataSourceMutation.isPending}
              >
                {wizardStep === 1 ? "Continue ->" : wizardStep === 2 ? "Test & Review" : "Save & Connect"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
