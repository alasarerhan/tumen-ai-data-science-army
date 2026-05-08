import { useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { useAuth } from "../context/AuthContext";
import { getHitlItem, approveHitl, rejectHitl } from "../api/hitl";
import { Pause, ChevronDown, ChevronRight, Copy, CheckCircle2, XCircle, Clock } from "lucide-react";

const CODE_SAMPLE = `# Recommended Actions — NarrativeAgent v2.1.0
# Run: run_9a3f2b1c · Q4 Sales Pipeline Analysis

actions:
  - step: generate_executive_summary
    model: gpt-4o
    context_tokens: 14_203
    target_audience: C-suite
    
  - step: synthesize_recommendations
    top_n: 5
    scoring_method: ICE
    require_ab_test_design: true
    
  - step: finalize_report
    format: PDF
    include_visualizations: true
    confidence_threshold: 0.85`;

const APPROVAL_HISTORY = [
  { actor: "AI System", action: "Requested by AI — Awaiting initial approval", time: "12m ago" },
];

export default function HITLApproval() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const [showCode, setShowCode] = useState(false);
  const [modification, setModification] = useState("");
  const [confirmApprove, setConfirmApprove] = useState(false);
  const [countdown, setCountdown] = useState(47 * 60 + 23);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!id || !workspaceId) return;
    getHitlItem(id, workspaceId).catch((err: unknown) => {
      console.error("Failed to load HITL item:", err);
      return null;
    });
  }, [id, workspaceId]);

  const handleApprove = async () => {
    if (!id || !workspaceId) return;
    setSubmitting(true);
    await approveHitl(id, { workspace_id: workspaceId, comment: modification || undefined }).catch((err: unknown) => {
      console.error("Failed to approve HITL:", err);
      return null;
    });
    setSubmitting(false);
    setConfirmApprove(false);
    navigate(-1);
  };

  const handleReject = async () => {
    if (!id || !workspaceId) return;
    setSubmitting(true);
    await rejectHitl(id, { workspace_id: workspaceId, reason: modification || undefined }).catch((err: unknown) => {
      console.error("Failed to reject HITL:", err);
      return null;
    });
    setSubmitting(false);
    navigate(-1);
  };

  useEffect(() => {
    const t = setInterval(() => setCountdown((c) => Math.max(0, c - 1)), 1000);
    return () => clearInterval(t);
  }, []);

  const formatCountdown = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}m ${s.toString().padStart(2, "0")}s`;
  };

  return (
    <AppShell>
      <div className="p-6 max-w-[672px] mx-auto">
        <div className="bg-white dark:bg-slate-900 rounded-[12px] border border-slate-200 dark:border-slate-700 shadow-lg overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="approval-title">
          {/* Header */}
          <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-700 bg-amber-50 dark:bg-amber-900/10">
            <div className="flex items-center gap-2 mb-1">
              <Pause size={18} className="text-amber-600" />
              <h1 id="approval-title" className="text-amber-700 dark:text-amber-400" style={{ fontSize: "20px", fontWeight: 600 }}>
                Approval Required
              </h1>
            </div>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Run: <strong>Q4 Sales Pipeline Analysis</strong> · Sales Intelligence Pipeline v3
            </p>
            <div className="flex items-center gap-2 mt-2">
              <Clock size={13} className="text-amber-600" />
              <p className="text-sm text-amber-700 dark:text-amber-400" aria-live="polite" role="timer">
                Requested 12 minutes ago. Auto-expires in{" "}
                <span className="font-semibold tabular-nums">{formatCountdown(countdown)}</span>
              </p>
            </div>
          </div>

          <div className="px-6 py-5 space-y-5">
            {/* Section 1: Context */}
            <div className="bg-slate-50 dark:bg-slate-800 rounded-[8px] border border-slate-200 dark:border-slate-700 p-4 space-y-3">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">What is being approved</h2>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                The NarrativeAgent is requesting permission to generate a full strategic executive report for the Q4 Sales Pipeline Analysis run. This will use GPT-4o to synthesize 14,203 context tokens into a PDF report with ICE-scored recommendations and A/B test designs.
              </p>
              <div className="flex flex-wrap gap-1.5">
                {["Q4 Sales", "Executive Report", "GPT-4o", "ICE Scoring"].map((e) => (
                  <span key={e} className="text-xs px-2 py-0.5 bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-700 rounded-full">
                    {e}
                  </span>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Risk Level:</span>
                <Badge variant="warning" size="sm" dot>Medium</Badge>
              </div>
            </div>

            {/* Section 2: Recommended Steps */}
            <div>
              <button
                onClick={() => setShowCode(!showCode)}
                className="w-full flex items-center justify-between text-sm font-medium text-slate-700 dark:text-slate-300 mb-2"
              >
                Recommended Steps
                {showCode ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                <span className="ml-auto text-xs text-indigo-600 dark:text-indigo-400 mr-2">{showCode ? "Hide" : "Show"} Details</span>
              </button>
              {showCode && (
                <div className="relative">
                  <pre className="bg-slate-900 text-slate-300 p-4 rounded-[8px] text-[12px] font-mono overflow-x-auto whitespace-pre">
                    {CODE_SAMPLE}
                  </pre>
                  <button
                    onClick={() => navigator.clipboard.writeText(CODE_SAMPLE)}
                    className="absolute top-2 right-2 p-1.5 rounded bg-slate-700 text-slate-400 hover:text-slate-200 hover:bg-slate-600"
                    aria-label="Copy code"
                  >
                    <Copy size={12} />
                  </button>
                </div>
              )}
            </div>

            {/* Section 3: History */}
            <div>
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-3">Approval History</h2>
              <div className="space-y-2">
                {APPROVAL_HISTORY.map((item, idx) => (
                  <div key={idx} className="flex items-start gap-3">
                    <div className="size-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-xs font-semibold text-slate-600">
                      AI
                    </div>
                    <div>
                      <p className="text-sm text-slate-700 dark:text-slate-300">
                        <span className="font-medium">{item.actor}</span>{" "}
                        <span className="text-slate-500">{item.action}</span>
                      </p>
                      <p className="text-xs text-slate-400">{item.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Modification input */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700 dark:text-slate-300">
                Request Changes <span className="text-slate-400 font-normal">(optional)</span>
              </label>
              <div className="relative">
                <textarea
                  rows={3}
                  value={modification}
                  onChange={(e) => setModification(e.target.value.slice(0, 500))}
                  placeholder="Request changes or additional context… (optional)"
                  className="w-full px-3 py-2 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                />
                <span className="absolute bottom-2 right-3 text-[10px] text-slate-400 tabular-nums">
                  {modification.length}/500
                </span>
              </div>
            </div>
          </div>

          {/* Footer actions */}
          <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between">
            <Button variant="secondary" size="md">
              Request Changes
            </Button>
            <div className="flex gap-2">
              <Button variant="destructive" size="md" leadingIcon={<XCircle size={14} />} loading={submitting} onClick={handleReject}>
                Reject
              </Button>
              {!confirmApprove ? (
                <Button
                  variant="primary"
                  size="md"
                  className="bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-500"
                  leadingIcon={<CheckCircle2 size={14} />}
                  onClick={() => setConfirmApprove(true)}
                  aria-label="Approve this AI action"
                >
                  Approve
                </Button>
              ) : (
                <div className="flex items-center gap-2 px-3 py-2 bg-emerald-50 dark:bg-emerald-900/20 rounded-[6px] border border-emerald-200 dark:border-emerald-700">
                  <span className="text-sm text-emerald-700 dark:text-emerald-400">Confirm approval?</span>
                  <Button
                    variant="primary"
                    size="sm"
                    className="bg-emerald-600 hover:bg-emerald-700"
                    onClick={() => { setConfirmApprove(false); handleApprove(); }}
                  >
                    Yes, Approve
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setConfirmApprove(false)}>
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

