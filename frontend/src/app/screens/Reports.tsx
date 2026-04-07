import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";
import { getArtifacts, type Artifact } from "../api/artifacts";
import { BarChart2, Download, Link2, BookOpen } from "lucide-react";

export default function Reports() {
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [reports, setReports] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!workspaceId) return;
    setLoading(true);
    getArtifacts({ workspace_id: workspaceId, kind: "strategy_report" })
      .then((res) => setReports(res.items))
      .catch((err: unknown) => {
        console.error("Failed to load reports:", err);
        setReports([]);
      })
      .finally(() => setLoading(false));
  }, [workspaceId]);

  const displayName = (art: Artifact) => art.uri.split("/").pop() ?? art.id;
  const displayDate = (d: string | null) =>
    d
      ? new Date(d).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
      : "--";

  return (
    <AppShell>
      <div className="p-6 max-w-[1280px] mx-auto space-y-5">
        <div>
          <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
            Reports
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            AI-generated strategic reports from your pipeline runs.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading && <p className="text-sm text-slate-500">Loading reports…</p>}
          {!loading && reports.length === 0 && <p className="text-sm text-slate-400">No reports found.</p>}
          {reports.map((art) => (
            <div
              key={art.id}
              className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 shadow-sm hover:shadow-md transition-shadow cursor-pointer"
              onClick={() => navigate(`/reports/${art.id}`)}
            >
              <div className="p-5">
                <div className="flex items-start gap-3 mb-3">
                  <div className="size-10 rounded-[8px] bg-pink-50 dark:bg-pink-900/20 flex items-center justify-center flex-shrink-0">
                    <BarChart2 size={18} className="text-pink-500" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{displayName(art)}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{displayDate(art.created_at)}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1.5 mb-4">
                  <span className="text-[10px] px-2 py-0.5 bg-slate-100 dark:bg-slate-800 text-slate-500 rounded-full">{art.kind}</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-xs text-slate-400">Run ID:</span>
                  <code className="text-xs font-mono text-slate-500">{art.workflow_run_id ?? "—"}</code>
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 rounded ml-1">
                    AI-Generated
                  </span>
                </div>
              </div>
              <div className="px-5 py-2.5 border-t border-slate-100 dark:border-slate-800 flex gap-2">
                <Button variant="secondary" size="xs" leadingIcon={<BookOpen size={11} />} onClick={(e) => { e.stopPropagation(); navigate(`/reports/${art.id}`); }}>
                  Read Report
                </Button>
                <Button variant="ghost" size="xs" leadingIcon={<Download size={11} />} onClick={(e) => e.stopPropagation()}>
                  Download PDF
                </Button>
                <Button variant="ghost" size="xs" leadingIcon={<Link2 size={11} />} onClick={(e) => e.stopPropagation()}>
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


