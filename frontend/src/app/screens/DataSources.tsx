import React, { useEffect, useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { useAuth } from "../context/AuthContext";
import {
  getDataSources,
  createDataSource,
  deleteDataSource,
  testDataSource,
  type DataSource,
} from "../api/datasources";
import { formatRelativeTime } from "../utils/time";
import { cn } from "../lib/utils";
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
  degraded: { icon: <AlertTriangle size={12} />, color: "text-amber-500", label: "Degraded" },
  error: { icon: <AlertCircle size={12} />, color: "text-red-500", label: "Error" },
};

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
  { id: "local", label: "Local File", icon: <FileText size={20} />, desc: "CSV, Excel, Parquet, JSON files from local storage.", color: "text-emerald-600 bg-emerald-50" },
  { id: "sql", label: "SQL Database", icon: <Database size={20} />, desc: "PostgreSQL, MySQL, SQLite via SQLAlchemy.", color: "text-sky-600 bg-sky-50" },
  { id: "mcp", label: "MCP Plugin", icon: <Plug size={20} />, desc: "Custom connector via Model Context Protocol.", color: "text-violet-600 bg-violet-50" },
];

export default function DataSources() {
  const { workspaceId } = useAuth();
  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [loadingDs, setLoadingDs] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formUri, setFormUri] = useState("");
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const fetchDs = () => {
    if (!workspaceId) return;
    setLoadingDs(true);
    setPageError(null);
    getDataSources(workspaceId)
      .then((res) => setDataSources(res.items))
      .catch((err) => {
        setDataSources([]);
        setPageError(err instanceof Error ? err.message : "Failed to load data sources");
      })
      .finally(() => setLoadingDs(false));
  };
  useEffect(() => { fetchDs(); }, [workspaceId]);

  const handleDelete = async (id: string) => {
    if (!workspaceId) return;
    try {
      await deleteDataSource(id, workspaceId);
      fetchDs();
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : "Failed to delete data source");
    }
  };

  const handleTest = async (id: string) => {
    if (!workspaceId) return;
    setTestingId(id);
    try {
      await testDataSource(id, workspaceId);
    } catch (err: unknown) {
      setPageError(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setTestingId(null);
    }
  };

  const handleSave = async () => {
    if (!workspaceId || !formName || !selectedType) return;
    setSaving(true);
    try {
      await createDataSource({
        workspace_id: workspaceId,
        name: formName,
        kind: selectedType,
        connection_uri: formUri,
      });
      fetchDs();
      setShowModal(false);
      setWizardStep(1);
      setSelectedType(null);
      setFormName("");
      setFormUri("");
    } catch (err: unknown) {
      console.error("Failed to create data source:", err);
      setPageError("Failed to create data source");
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppShell>
      <div className="p-6 max-w-[1280px] mx-auto space-y-5">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
              Data Sources
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
              Connect your data to enable AI-powered analysis.
            </p>
          </div>
          <Button variant="primary" size="md" leadingIcon={<Plus size={14} />} onClick={() => setShowModal(true)}>
            Add Data Source
          </Button>
        </div>
        {pageError ? (
          <div className="rounded-[8px] border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {pageError}
          </div>
        ) : null}

        {/* Connector list */}
        <div className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden divide-y divide-slate-100 dark:divide-slate-800">
          {loadingDs && (
            <p className="py-12 text-center text-sm text-slate-400">Loading data sources...</p>
          )}
          {!loadingDs && dataSources.length === 0 && (
            <p className="py-12 text-center text-sm text-slate-400">No data sources connected yet.</p>
          )}
          {dataSources.map((ds) => {
            return (
              <div key={ds.id} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                {/* Icon */}
                <div className={cn("size-10 rounded-[8px] flex items-center justify-center flex-shrink-0", typeBg[ds.kind as keyof typeof typeBg] ?? "bg-slate-50")}>
                  {typeIcon[ds.kind as keyof typeof typeIcon] ?? <Database size={18} className="text-slate-500" />}
                </div>

                {/* Name & type */}
                <div className="w-48 flex-shrink-0">
                  <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{ds.name}</p>
                  <Badge variant={ds.kind === "sql" ? "info" : ds.kind === "mcp" ? "violet" : "success"} size="sm">
                    {ds.kind}
                  </Badge>
                </div>

                {/* Connection string */}
                <div className="flex-1 min-w-0">
                  <code className="text-xs font-mono text-slate-500 dark:text-slate-400 truncate block">{ds.connection_uri || "--"}</code>
                  <div className="flex items-center gap-1 mt-0.5 text-emerald-500">
                    {healthConfig.healthy.icon}
                    <span className="text-xs">{healthConfig.healthy.label}</span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs text-slate-400">Added: {formatRelativeTime(ds.created_at)}</span>
                  <Button variant="ghost" size="xs" loading={testingId === ds.id} onClick={() => handleTest(ds.id)}>Test Connection</Button>
                  <div className="relative">
                    <button
                      onClick={() => setOpenMenu(openMenu === ds.id ? null : ds.id)}
                      className="p-1.5 rounded text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                      aria-label={`${ds.name} actions`}
                    >
                      <MoreHorizontal size={15} />
                    </button>
                    {openMenu === ds.id && (
                      <div className="absolute right-0 top-full mt-1 z-20 w-36 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-[8px] shadow-md py-1">
                        {[
                          { label: "Edit", icon: <Edit size={13} /> },
                          { label: "Duplicate", icon: <Copy size={13} /> },
                          { label: "Delete", icon: <Trash2 size={13} />, danger: true, action: () => handleDelete(ds.id) },
                        ].map((item) => (
                          <button
                            key={item.label}
                            onClick={() => { item.action?.(); setOpenMenu(null); }}
                            className={cn(
                              "w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-700",
                              item.danger ? "text-red-600" : "text-slate-700 dark:text-slate-200"
                            )}
                          >
                            {item.icon}
                            {item.label}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Add Data Source Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => { setShowModal(false); setWizardStep(1); setSelectedType(null); }} />
          <div className="relative bg-white dark:bg-slate-900 rounded-[12px] shadow-xl w-full max-w-[560px] mx-4" role="dialog" aria-modal="true" aria-label="Add Data Source">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">Add Data Source</h2>
              <button onClick={() => { setShowModal(false); setWizardStep(1); setSelectedType(null); }} className="p-1.5 rounded text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Close">
                <X size={16} />
              </button>
            </div>

            <div className="px-6 py-5">
              {wizardStep === 1 && (
                <div className="space-y-3">
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">Choose your data source type:</p>
                  {WIZARD_TYPES.map((type) => (
                    <button
                      key={type.id}
                      onClick={() => setSelectedType(type.id)}
                      className={cn(
                        "w-full flex items-start gap-4 p-4 rounded-[8px] border-2 transition-all text-left",
                        selectedType === type.id
                          ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20"
                          : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                      )}
                    >
                      <div className={cn("size-10 rounded-[8px] flex items-center justify-center flex-shrink-0", type.color.split(" ")[1])}>
                        <span className={type.color.split(" ")[0]}>{type.icon}</span>
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{type.label}</p>
                          {selectedType === type.id && <CheckCircle2 size={16} className="text-indigo-600" />}
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">{type.desc}</p>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {wizardStep === 2 && selectedType === "local" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Display Name</label>
                    <input className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="My CSV Store" value={formName} onChange={(e) => setFormName(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Base Directory</label>
                    <input className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="/data/uploads" value={formUri} onChange={(e) => setFormUri(e.target.value)} />
                  </div>
                  <Button variant="ghost" size="sm">Test Connection -&gt;</Button>
                </div>
              )}

              {wizardStep === 2 && selectedType === "sql" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Display Name</label>
                    <input className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Production DB" value={formName} onChange={(e) => setFormName(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Connection URI</label>
                    <input type="password" autoComplete="off" spellCheck={false} className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="postgresql+psycopg2://user:pass@host/db" value={formUri} onChange={(e) => setFormUri(e.target.value)} />
                    <p className="text-[10px] text-slate-400">Format: postgresql+psycopg2://user:pass@host/db</p>
                  </div>
                  <Button variant="ghost" size="sm">Test Connection -&gt;</Button>
                </div>
              )}

              {wizardStep === 2 && selectedType === "mcp" && (
                <div className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Plugin Name</label>
                    <input className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Module Path</label>
                    <input className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" placeholder="mypackage.connectors.custom" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400">Config (JSON)</label>
                    <textarea rows={3} className="w-full px-3 py-2 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none font-mono text-xs" placeholder='{"api_key": "..."}' />
                  </div>
                </div>
              )}

              {wizardStep === 3 && (
                <div className="space-y-4">
                  <div className="bg-slate-50 dark:bg-slate-800 rounded-[8px] p-4 space-y-2 text-sm">
                    <p className="font-medium text-slate-800 dark:text-slate-200 mb-3">Review & Save</p>
                    {[["Type", WIZARD_TYPES.find((t) => t.id === selectedType)?.label || ""], ["Name", "My Data Source"], ["Status", "Ready to connect"]].map(([label, value]) => (
                      <div key={label} className="flex gap-3">
                        <span className="text-slate-400 w-16">{label}</span>
                        <span className="text-slate-700 dark:text-slate-300">{value}</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 p-3 rounded-[6px] bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-700">
                    <CheckCircle2 size={14} className="text-emerald-600" />
                    <span className="text-xs text-emerald-700 dark:text-emerald-400">Connection test successful</span>
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex justify-between">
              <Button variant="ghost" size="md" onClick={() => wizardStep > 1 ? setWizardStep(wizardStep - 1) : setShowModal(false)}>
                {wizardStep > 1 ? "Back" : "Cancel"}
              </Button>
              <Button
                variant="primary"
                size="md"
                disabled={wizardStep === 1 && !selectedType}
                onClick={() => {
                  if (wizardStep < 3) setWizardStep(wizardStep + 1);
                  else handleSave();
                }}
                loading={saving}
              >
                {wizardStep === 1 ? "Continue ->" : wizardStep === 2 ? "Review ->" : "Save & Connect"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}



