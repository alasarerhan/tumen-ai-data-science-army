import { useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { cn } from "../lib/utils";
import { Download, Link2, Share2, ChevronDown, ChevronRight } from "lucide-react";

const SECTIONS = ["Context", "Findings", "Summary", "Recommendations"] as const;
type Section = typeof SECTIONS[number];

const FINDINGS = [
  { rank: 1, medal: "🥇", title: "Churn rate highest in enterprise segment", metric: "Churn Rate", before: "12.4%", after: "18.7%", delta: "+50.8%" },
  { rank: 2, medal: "🥈", title: "Feature importance: tenure_months dominates prediction", metric: "Feature Weight", before: "0.31", after: "0.31", delta: "—" },
  { rank: 3, medal: "🥉", title: "Model AUC significantly above baseline", metric: "AUC Score", before: "0.71 (prev)", after: "0.924", delta: "+30.1%" },
];

const RECOMMENDATIONS = [
  {
    num: 1,
    title: "Launch proactive retention campaign for enterprise accounts",
    impact: 9,
    confidence: 8,
    ease: 6,
    ice: 432,
    description: "Target the top 200 at-risk enterprise customers identified by the ML model with personalized outreach from customer success managers within the next 30 days.",
  },
  {
    num: 2,
    title: "Introduce tenure-based loyalty program",
    impact: 7,
    confidence: 8,
    ease: 7,
    ice: 392,
    description: "Create milestone rewards at 12, 24, and 36 months of tenure to incentivize continued engagement and reduce churn in the critical early stages.",
  },
  {
    num: 3,
    title: "A/B test pricing for annual vs. monthly billing",
    impact: 8,
    confidence: 6,
    ease: 5,
    ice: 240,
    description: "Test an enhanced annual discount (20% → 30%) for enterprise segment to increase commitment length and reduce month-to-month churn risk.",
  },
  {
    num: 4,
    title: "Improve onboarding for accounts with < 6 months tenure",
    impact: 7,
    confidence: 7,
    ease: 8,
    ice: 392,
    description: "Redesign the 30/60/90 day onboarding experience for new enterprise accounts. The model indicates this cohort has 2.3x higher churn probability.",
  },
];

function ScoreBadge({ label, value }: { label: string; value: number }) {
  const color = value >= 8 ? "text-emerald-600 bg-emerald-50" : value >= 6 ? "text-indigo-600 bg-indigo-50" : "text-amber-600 bg-amber-50";
  return (
    <div className="flex flex-col items-center gap-0.5">
      <span className={cn("text-sm font-semibold tabular-nums px-2 py-0.5 rounded", color)}>{value}</span>
      <span className="text-[10px] text-slate-400 uppercase">{label}</span>
    </div>
  );
}

export default function StrategicReport() {
  const [activeSection, setActiveSection] = useState<Section>("Context");
  const [expandedRec, setExpandedRec] = useState<number | null>(null);
  const [showABTest, setShowABTest] = useState(false);

  return (
    <AppShell>
      <div className="flex min-h-full">
        {/* Main report body */}
        <div className="flex-1 overflow-auto">
          {/* Report Header */}
          <div className="bg-gradient-to-b from-indigo-50 to-white dark:from-indigo-950/30 dark:to-slate-900 border-b border-slate-200 dark:border-slate-700 px-6 py-8">
            <div className="max-w-[840px] mx-auto">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 dark:text-indigo-400 rounded">AI-Generated</span>
                <code className="text-xs font-mono text-slate-400">run_7e8c4d5f</code>
              </div>
              <h1 className="text-slate-900 dark:text-slate-50 mb-2" style={{ fontSize: "36px", fontWeight: 700, lineHeight: "44px", textWrap: "balance" }}>
                Customer Churn Analysis — December 2025
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">
                Generated on {new Intl.DateTimeFormat("en-US", { month: "long", day: "numeric", year: "numeric" }).format(new Date(Date.now() - 1000 * 60 * 60 * 2))}
              </p>
              <div className="flex flex-wrap gap-1.5 mb-5">
                {["Churn", "Customer", "ML", "Retention", "Enterprise", "Q4 2025"].map((tag) => (
                  <span key={tag} className="text-xs px-2.5 py-1 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full text-slate-600 dark:text-slate-300">
                    {tag}
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" leadingIcon={<Download size={13} />}>Download PDF</Button>
                <Button variant="ghost" size="sm" leadingIcon={<Link2 size={13} />}>Copy Link</Button>
                <Button variant="ghost" size="sm" leadingIcon={<Share2 size={13} />}>Share</Button>
              </div>
            </div>
          </div>

          {/* Report content */}
          <div className="max-w-[840px] mx-auto px-6 py-8 space-y-8">
            {/* Stage 1: Context */}
            <section id="context">
              <div className="border-l-4 pl-5 rounded-r-[8px] bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 p-5" style={{ borderLeftColor: "#ec4899" }}>
                <h2 className="text-slate-900 dark:text-slate-100 mb-3" style={{ fontSize: "20px", fontWeight: 600 }}>Business Context</h2>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  {["Customer Churn", "Enterprise Accounts", "SaaS Metrics", "Q4 2025", "Retention Strategy"].map((entity) => (
                    <span key={entity} className="text-xs px-2 py-0.5 bg-pink-50 dark:bg-pink-900/20 text-pink-700 dark:text-pink-400 border border-pink-200 dark:border-pink-800 rounded-full">
                      {entity}
                    </span>
                  ))}
                </div>
                <div className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
                  <p><strong className="text-slate-800 dark:text-slate-200">Objective:</strong> Identify key drivers of customer churn in the enterprise segment and provide actionable recommendations to reduce churn rate by Q2 2026.</p>
                  <p><strong className="text-slate-800 dark:text-slate-200">Dataset:</strong> 44,908 customer records, January 2024 – December 2025.</p>
                </div>
                <div className="mt-3 flex items-center gap-2">
                  <span className="text-xs text-slate-500">Context Confidence</span>
                  <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                    <div className="h-full bg-pink-500 rounded-full" style={{ width: "92%" }} />
                  </div>
                  <span className="text-xs font-medium text-slate-600 dark:text-slate-300 tabular-nums">92%</span>
                </div>
              </div>
            </section>

            {/* Stage 2: Findings */}
            <section id="findings">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-[8px] p-5">
                <h2 className="text-slate-900 dark:text-slate-100 mb-4" style={{ fontSize: "20px", fontWeight: 600 }}>Key Findings</h2>
                <div className="space-y-3 mb-5">
                  {FINDINGS.map((finding) => (
                    <div key={finding.rank} className="flex items-start gap-3 p-3 rounded-[6px] bg-slate-50 dark:bg-slate-800">
                      <span className="text-xl flex-shrink-0">{finding.medal}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{finding.title}</p>
                        <p className="text-xs text-slate-400 mt-0.5">{finding.metric}</p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <p className="text-xs tabular-nums text-slate-500">{finding.before} → {finding.after}</p>
                        <p className={cn("text-xs font-medium tabular-nums", finding.delta.startsWith("+") ? "text-emerald-600" : "text-slate-400")}>
                          {finding.delta}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                {/* Metrics table */}
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-2">Merged Metrics</h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 dark:border-slate-800">
                      {["Metric", "Value", "Baseline", "Δ"].map((h) => (
                        <th key={h} className="pb-2 text-left font-medium text-slate-400 uppercase">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {[
                      ["Model AUC", "0.924", "0.710", "+30.1%"],
                      ["Precision", "0.891", "0.682", "+30.6%"],
                      ["Recall", "0.887", "0.701", "+26.5%"],
                      ["F1 Score", "0.889", "0.690", "+28.8%"],
                      ["Churn Rate (Enterprise)", "18.7%", "12.4%", "+50.8%"],
                    ].map(([metric, val, base, delta]) => (
                      <tr key={metric}>
                        <td className="py-2 text-slate-700 dark:text-slate-300 font-medium">{metric}</td>
                        <td className="py-2 tabular-nums text-slate-600 dark:text-slate-300">{val}</td>
                        <td className="py-2 tabular-nums text-slate-400">{base}</td>
                        <td className={cn("py-2 tabular-nums font-medium", delta.startsWith("+") ? "text-emerald-600" : "text-red-600")}>{delta}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Stage 3: Narrative */}
            <section id="summary">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-[8px] p-5">
                <h2 className="text-slate-900 dark:text-slate-100 mb-4" style={{ fontSize: "30px", fontWeight: 600, lineHeight: "38px" }}>
                  Executive Summary
                </h2>
                <div className="space-y-4 text-slate-600 dark:text-slate-400" style={{ fontSize: "16px", lineHeight: "28px" }}>
                  <p style={{ textWrap: "pretty" }}>
                    Our analysis of 44,908 customer records reveals a <strong className="text-slate-800 dark:text-slate-200">statistically significant increase in enterprise-segment churn</strong> over the past 12 months. The churn rate has risen from 12.4% to 18.7%, representing a 50.8% relative increase that demands immediate strategic attention.
                  </p>

                  {/* Pull quote */}
                  <blockquote className="border-l-4 border-indigo-500 pl-4 py-1 italic text-slate-700 dark:text-slate-300" style={{ fontSize: "18px", lineHeight: "28px" }}>
                    "The single most powerful predictor of churn is customer tenure — accounts under 18 months are 2.3× more likely to churn than established accounts."
                  </blockquote>

                  <p style={{ textWrap: "pretty" }}>
                    The H2O AutoML model achieved an AUC of 0.924, significantly outperforming our previous logistic regression baseline (0.710). Feature importance analysis consistently surfaces <code className="text-xs px-1 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">tenure_months</code>, <code className="text-xs px-1 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">support_tickets_90d</code>, and <code className="text-xs px-1 py-0.5 bg-slate-100 dark:bg-slate-800 rounded">feature_adoption_rate</code> as the dominant predictors.
                  </p>

                  <h3 className="text-slate-800 dark:text-slate-200" style={{ fontSize: "18px", fontWeight: 600 }}>
                    Segment Analysis
                  </h3>
                  <p style={{ textWrap: "pretty" }}>
                    Enterprise accounts with annual contract values above $50k and tenure under 18 months represent the highest-risk cohort, comprising 34% of predicted churners despite being only 12% of total enterprise customers.
                  </p>
                </div>
              </div>
            </section>

            {/* Stage 4: Recommendations */}
            <section id="recommendations">
              <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-[8px] p-5">
                <h2 className="text-slate-900 dark:text-slate-100 mb-5" style={{ fontSize: "20px", fontWeight: 600 }}>
                  Strategic Recommendations
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {RECOMMENDATIONS.map((rec) => (
                    <div key={rec.num} className="border border-slate-200 dark:border-slate-700 rounded-[8px] p-4">
                      <div className="flex items-start justify-between mb-2">
                        <span className="size-6 rounded-full bg-indigo-100 dark:bg-indigo-900/40 text-indigo-700 dark:text-indigo-300 text-xs font-semibold flex items-center justify-center flex-shrink-0">
                          {rec.num}
                        </span>
                        <span className="text-lg font-semibold text-indigo-600 dark:text-indigo-400 tabular-nums">{rec.ice}</span>
                      </div>
                      <p className="text-sm font-medium text-slate-800 dark:text-slate-200 mb-2">{rec.title}</p>
                      <div className="flex gap-3 mb-3">
                        <ScoreBadge label="Impact" value={rec.impact} />
                        <ScoreBadge label="Conf." value={rec.confidence} />
                        <ScoreBadge label="Ease" value={rec.ease} />
                      </div>
                      <p className={cn("text-xs text-slate-500 dark:text-slate-400", expandedRec !== rec.num && "line-clamp-2")}>
                        {rec.description}
                      </p>
                      <button
                        onClick={() => setExpandedRec(expandedRec === rec.num ? null : rec.num)}
                        className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline mt-1"
                      >
                        {expandedRec === rec.num ? "Show less" : "Show more"}
                      </button>
                    </div>
                  ))}
                </div>

                {/* A/B Test section */}
                <div className="mt-5 border border-slate-100 dark:border-slate-800 rounded-[6px] overflow-hidden">
                  <button
                    onClick={() => setShowABTest(!showABTest)}
                    className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    A/B Test Design
                    {showABTest ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  </button>
                  {showABTest && (
                    <div className="px-4 pb-4 space-y-2 text-sm">
                      {[
                        ["Hypothesis", "Annual discount increase (30%) will reduce enterprise churn by ≥15% in 90 days"],
                        ["Control", "Current annual discount: 20%"],
                        ["Test Variant", "Enhanced annual discount: 30%"],
                        ["Success Metric", "90-day churn rate reduction ≥15%"],
                        ["Sample Size", "400 enterprise accounts (200 per arm)"],
                        ["Duration", "90 days"],
                      ].map(([label, value]) => (
                        <div key={label} className="flex gap-3">
                          <span className="text-slate-400 w-32 flex-shrink-0">{label}</span>
                          <span className="text-slate-700 dark:text-slate-300">{value}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
        </div>

        {/* Floating ToC */}
        <aside className="hidden xl:block w-52 flex-shrink-0 py-8 pr-6">
          <div className="sticky top-8">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Contents</p>
            <nav className="space-y-1">
              {SECTIONS.map((section) => (
                <a
                  key={section}
                  href={`#${section.toLowerCase()}`}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors",
                    activeSection === section
                      ? "text-indigo-600 dark:text-indigo-400 border-l-2 border-indigo-600 pl-2.5"
                      : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  )}
                  onClick={() => setActiveSection(section)}
                >
                  {section}
                </a>
              ))}
            </nav>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}

