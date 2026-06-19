import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router";
import {
  Activity,
  BarChart2,
  BookOpen,
  Boxes,
  Database,
  Download,
  FileText,
  GitBranch,
  Layers3,
  Link2,
  Network,
} from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";
import { getArtifacts, type Artifact } from "../api/artifacts";

const REPORT_KINDS = new Set(["strategy_report", "report", "evaluation_report"]);

function displayName(artifact: Artifact) {
  return artifact.uri.split("/").pop() ?? artifact.id;
}

function displayDate(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
    : "--";
}

function shortId(value: string | null | undefined) {
  if (!value) return "--";
  return value.length > 10 ? value.slice(0, 10) : value;
}

function kindLabel(kind: string) {
  return kind.replace(/_/g, " ");
}

export default function Reports() {
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!workspaceId) {
      setArtifacts([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    getArtifacts({ workspace_id: workspaceId, limit: 100 })
      .then((res) => setArtifacts(res.items))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to load artifacts";
        console.error("Failed to load artifacts:", err);
        setError(message);
        setArtifacts([]);
      })
      .finally(() => setLoading(false));
  }, [workspaceId]);

  const reports = useMemo(() => artifacts.filter((artifact) => REPORT_KINDS.has(artifact.kind)), [artifacts]);
  const artifactsById = useMemo(() => new Map(artifacts.map((artifact) => [artifact.id, artifact])), [artifacts]);
  const kindGroups = useMemo(() => {
    const groups = new Map<string, Artifact[]>();
    artifacts.forEach((artifact) => {
      const next = groups.get(artifact.kind) ?? [];
      next.push(artifact);
      groups.set(artifact.kind, next);
    });
    return Array.from(groups.entries())
      .map(([kind, items]) => ({ kind, items }))
      .sort((a, b) => b.items.length - a.items.length || a.kind.localeCompare(b.kind));
  }, [artifacts]);
  const lineageEdges = useMemo(
    () =>
      artifacts.flatMap((artifact) =>
        artifact.parent_artifact_ids.map((parentId) => ({
          id: `${parentId}-${artifact.id}`,
          parentId,
          child: artifact,
          parent: artifactsById.get(parentId),
        })),
      ),
    [artifacts, artifactsById],
  );
  const sourceArtifacts = useMemo(
    () => artifacts.filter((artifact) => artifact.parent_artifact_ids.length === 0).slice(0, 6),
    [artifacts],
  );
  const linkedArtifactCount = artifacts.filter((artifact) => artifact.parent_artifact_ids.length > 0).length;
  const modelCount = artifacts.filter((artifact) => artifact.kind === "model").length;

  const refreshArtifacts = () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    getArtifacts({ workspace_id: workspaceId, limit: 100 })
      .then((res) => setArtifacts(res.items))
      .catch((err: unknown) => {
        const message = err instanceof Error ? err.message : "Failed to load artifacts";
        setError(message);
      })
      .finally(() => setLoading(false));
  };

  const copyArtifactLink = (artifactId: string) => {
    void navigator.clipboard?.writeText(`${window.location.origin}/reports/${artifactId}`);
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-[1280px] space-y-5 p-6">
        <div>
          <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
            Reports & Artifacts
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Pipeline outputs, reports, models, metrics, and artifact lineage across workspace runs.
          </p>
        </div>

        <div className="rounded-[8px] border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-4 py-3 dark:border-slate-800">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
                <Boxes size={15} className="text-indigo-500" />
                Pipeline Output Board
              </h2>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                Recent artifacts grouped by output type with run, node, and lineage context.
              </p>
            </div>
            <Button variant="secondary" size="xs" leadingIcon={<Activity size={12} />} disabled={loading} onClick={refreshArtifacts}>
              Refresh
            </Button>
          </div>

          <div className="grid grid-cols-2 border-b border-slate-100 text-xs dark:border-slate-800 sm:grid-cols-4">
            <div className="px-4 py-3">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><Layers3 size={13} /> Artifacts</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{artifacts.length}</p>
            </div>
            <div className="border-l border-slate-100 px-4 py-3 dark:border-slate-800">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><FileText size={13} /> Reports</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{reports.length}</p>
            </div>
            <div className="border-l border-slate-100 px-4 py-3 dark:border-slate-800">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><Database size={13} /> Models</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{modelCount}</p>
            </div>
            <div className="border-l border-slate-100 px-4 py-3 dark:border-slate-800">
              <p className="flex items-center gap-1.5 font-medium uppercase text-slate-400"><Network size={13} /> Linked</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 dark:text-slate-100">{linkedArtifactCount}</p>
            </div>
          </div>

          {loading ? (
            <div className="px-4 py-5 text-sm text-slate-500 dark:text-slate-400" role="status" aria-live="polite" aria-busy="true">Loading artifacts…</div>
          ) : error ? (
            <div className="px-4 py-5 text-sm text-rose-600 dark:text-rose-300">{error}</div>
          ) : artifacts.length === 0 ? (
            <div className="px-4 py-5 text-sm text-slate-500 dark:text-slate-400">No pipeline artifacts found.</div>
          ) : (
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {kindGroups.map((group) => (
                <div key={group.kind} className="grid gap-3 px-4 py-3 md:grid-cols-[180px_minmax(0,1fr)]">
                  <div>
                    <p className="text-sm font-semibold capitalize text-slate-800 dark:text-slate-100">{kindLabel(group.kind)}</p>
                    <p className="mt-1 text-xs text-slate-400">{group.items.length} outputs</p>
                  </div>
                  <div className="grid gap-2 lg:grid-cols-2">
                    {group.items.slice(0, 4).map((artifact) => (
                      <button
                        key={artifact.id}
                        type="button"
                        className="min-w-0 rounded-[6px] border border-slate-200 bg-slate-50 px-3 py-2 text-left transition-colors hover:border-indigo-200 hover:bg-indigo-50 dark:border-slate-700 dark:bg-slate-800/60 dark:hover:border-indigo-700 dark:hover:bg-indigo-950/30"
                        onClick={() => navigate(`/reports/${artifact.id}`)}
                      >
                        <span className="block truncate text-sm font-medium text-slate-800 dark:text-slate-100">{displayName(artifact)}</span>
                        <span className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500 dark:text-slate-400">
                          <span>run {shortId(artifact.workflow_run_id)}</span>
                          <span>node {artifact.produced_by_node_id ?? "--"}</span>
                          <span>{artifact.parent_artifact_ids.length} parents</span>
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-[8px] border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <div className="border-b border-slate-100 px-4 py-3 dark:border-slate-800">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-slate-100">
              <GitBranch size={15} className="text-indigo-500" />
              Artifact Lineage Graph
            </h2>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
              Parent-child artifact flow from source data through features, models, metrics, reports, and exports.
            </p>
          </div>

          {loading ? (
            <div className="px-4 py-5 text-sm text-slate-500 dark:text-slate-400" role="status" aria-live="polite" aria-busy="true">Loading lineage…</div>
          ) : lineageEdges.length === 0 ? (
            <div className="px-4 py-5 text-sm text-slate-500 dark:text-slate-400">No artifact lineage edges available yet.</div>
          ) : (
            <div className="grid gap-4 px-4 py-4 lg:grid-cols-[240px_minmax(0,1fr)]">
              <div>
                <p className="mb-2 text-xs font-medium uppercase text-slate-400">Source artifacts</p>
                <div className="space-y-2">
                  {sourceArtifacts.map((artifact) => (
                    <button
                      key={artifact.id}
                      type="button"
                      className="w-full min-w-0 rounded-[6px] border border-slate-200 px-3 py-2 text-left text-xs hover:border-indigo-200 hover:bg-indigo-50 dark:border-slate-700 dark:hover:border-indigo-700 dark:hover:bg-indigo-950/30"
                      onClick={() => navigate(`/reports/${artifact.id}`)}
                    >
                      <span className="block truncate font-medium text-slate-700 dark:text-slate-200">{displayName(artifact)}</span>
                      <span className="mt-0.5 block truncate text-slate-400">{kindLabel(artifact.kind)}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                {lineageEdges.slice(0, 12).map((edge) => (
                  <div
                    key={edge.id}
                    className="grid min-w-0 items-center gap-2 rounded-[6px] border border-slate-200 px-3 py-2 text-xs dark:border-slate-700 md:grid-cols-[minmax(0,1fr)_32px_minmax(0,1fr)]"
                  >
                    <button type="button" className="min-w-0 text-left" onClick={() => edge.parent && navigate(`/reports/${edge.parent.id}`)}>
                      <span className="block truncate font-medium text-slate-700 dark:text-slate-200">
                        {edge.parent ? displayName(edge.parent) : shortId(edge.parentId)}
                      </span>
                      <span className="mt-0.5 block truncate text-slate-400">{edge.parent ? kindLabel(edge.parent.kind) : "external parent"}</span>
                    </button>
                    <div className="hidden justify-center text-slate-300 md:flex">-&gt;</div>
                    <button type="button" className="min-w-0 text-left" onClick={() => navigate(`/reports/${edge.child.id}`)}>
                      <span className="block truncate font-medium text-slate-700 dark:text-slate-200">{displayName(edge.child)}</span>
                      <span className="mt-0.5 block truncate text-slate-400">
                        {kindLabel(edge.child.kind)} via {edge.child.produced_by_node_id ?? "--"}
                      </span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {loading && <p className="text-sm text-slate-500" role="status" aria-live="polite" aria-busy="true">Loading reports…</p>}
          {!loading && reports.length === 0 && <p className="text-sm text-slate-400">No reports found.</p>}
          {reports.map((artifact) => (
            <div
              key={artifact.id}
              className="cursor-pointer rounded-[8px] border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md dark:border-slate-700 dark:bg-slate-900"
              onClick={() => navigate(`/reports/${artifact.id}`)}
            >
              <div className="p-5">
                <div className="mb-3 flex items-start gap-3">
                  <div className="flex size-10 flex-shrink-0 items-center justify-center rounded-[8px] bg-pink-50 dark:bg-pink-900/20">
                    <BarChart2 size={18} className="text-pink-500" />
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-200">{displayName(artifact)}</p>
                    <p className="mt-0.5 text-xs text-slate-400">{displayDate(artifact.created_at)}</p>
                  </div>
                </div>
                <div className="mb-4 flex flex-wrap gap-1.5">
                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800">{artifact.kind}</span>
                  {artifact.parent_artifact_ids.length > 0 ? (
                    <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
                      {artifact.parent_artifact_ids.length} lineage parents
                    </span>
                  ) : null}
                </div>
                <div className="flex min-w-0 items-center gap-1">
                  <span className="text-xs text-slate-400">Run ID:</span>
                  <code className="truncate font-mono text-xs text-slate-500">{artifact.workflow_run_id ?? "--"}</code>
                  <span className="ml-1 inline-flex items-center gap-1 rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] text-indigo-600 dark:bg-indigo-900/20 dark:text-indigo-400">
                    AI-Generated
                  </span>
                </div>
              </div>
              <div className="flex gap-2 border-t border-slate-100 px-5 py-2.5 dark:border-slate-800">
                <Button variant="secondary" size="xs" leadingIcon={<BookOpen size={11} />} onClick={(event) => { event.stopPropagation(); navigate(`/reports/${artifact.id}`); }}>
                  Read Report
                </Button>
                <Button variant="ghost" size="xs" leadingIcon={<Download size={11} />} onClick={(event) => event.stopPropagation()}>
                  Download PDF
                </Button>
                <Button variant="ghost" size="xs" leadingIcon={<Link2 size={11} />} onClick={(event) => { event.stopPropagation(); copyArtifactLink(artifact.id); }}>
                  Copy Link
                </Button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
