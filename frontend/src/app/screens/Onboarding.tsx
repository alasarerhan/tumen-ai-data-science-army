import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { Button } from "../components/ui/button";
import { cn } from "../lib/utils";
import { Zap, CheckCircle2, GitBranch, BookOpen, Play } from "lucide-react";

const STEPS = ["Create Workspace", "Connect Data", "Invite Teammates", "You're all set!"] as const;

export default function Onboarding() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [workspaceName, setWorkspaceName] = useState("");
  const [slug, setSlug] = useState("");
  const [showConfetti, setShowConfetti] = useState(false);
  const [emails, setEmails] = useState<string[]>([]);
  const [emailInput, setEmailInput] = useState("");

  useEffect(() => {
    setSlug(workspaceName.toLowerCase().replace(/\s+/g, "-").replace(/[^a-z0-9-]/g, ""));
  }, [workspaceName]);

  useEffect(() => {
    if (step === 4) {
      setShowConfetti(true);
      const t = setTimeout(() => setShowConfetti(false), 3000);
      return () => clearTimeout(t);
    }
  }, [step]);

  const addEmail = () => {
    if (emailInput.trim() && !emails.includes(emailInput.trim())) {
      setEmails([...emails, emailInput.trim()]);
      setEmailInput("");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 flex flex-col items-center justify-center p-6 font-[Inter,sans-serif]">
      {/* Confetti */}
      {showConfetti && (
        <div className="fixed inset-0 pointer-events-none z-50 overflow-hidden">
          {Array.from({ length: 40 }).map((_, i) => (
            <div
              key={i}
              className="absolute animate-bounce"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                width: `${Math.random() * 10 + 5}px`,
                height: `${Math.random() * 10 + 5}px`,
                backgroundColor: ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#06b6d4"][Math.floor(Math.random() * 5)],
                borderRadius: Math.random() > 0.5 ? "50%" : "0",
                animationDelay: `${Math.random() * 0.5}s`,
                transform: `rotate(${Math.random() * 360}deg)`,
              }}
            />
          ))}
        </div>
      )}

      {/* Logo */}
      <div className="flex items-center gap-2.5 mb-8">
        <div className="size-8 bg-indigo-600 rounded-[8px] flex items-center justify-center">
          <Zap size={16} className="text-white" />
        </div>
        <span className="text-slate-900 dark:text-slate-50 font-semibold text-base">Insight Platform</span>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-8">
        {STEPS.map((label, idx) => {
          const num = idx + 1;
          const isCompleted = step > num;
          const isCurrent = step === num;
          return (
            <React.Fragment key={label}>
              <div className="flex flex-col items-center gap-1">
                <div className={cn(
                  "size-7 rounded-full text-xs font-semibold flex items-center justify-center transition-all",
                  isCompleted ? "bg-emerald-500 text-white" : isCurrent ? "bg-indigo-600 text-white ring-4 ring-indigo-100 dark:ring-indigo-900/50" : "bg-slate-200 dark:bg-slate-700 text-slate-500"
                )}>
                  {isCompleted ? <CheckCircle2 size={14} /> : num}
                </div>
                <span className={cn("text-[10px] whitespace-nowrap hidden sm:block", isCurrent ? "text-slate-800 dark:text-slate-200 font-medium" : "text-slate-400")}>
                  {label}
                </span>
              </div>
              {idx < STEPS.length - 1 && (
                <div className={cn("w-12 h-px", step > num ? "bg-emerald-400" : "bg-slate-200 dark:bg-slate-700")} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Card */}
      <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-[12px] border border-slate-200 dark:border-slate-700 shadow-lg overflow-hidden">
        {step === 1 && (
          <div className="p-7 space-y-5">
            <div>
              <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "24px", fontWeight: 700 }}>Create your workspace</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Give your team a home on Insight Platform.</p>
            </div>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Workspace Name</label>
                <input
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  placeholder="ACME Analytics"
                />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Slug</label>
                <div className="flex items-center h-9 px-3 rounded-[6px] border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800">
                  <span className="text-slate-400 text-sm">insight.ai/</span>
                  <span className="text-sm font-mono text-slate-700 dark:text-slate-200">{slug || "your-workspace"}</span>
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Region</label>
                <select className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                  <option>us-east-1 (N. Virginia)</option>
                  <option>eu-west-1 (Ireland)</option>
                  <option>ap-southeast-1 (Singapore)</option>
                </select>
              </div>
            </div>
            <Button variant="primary" size="lg" fullWidth disabled={!workspaceName.trim()} onClick={() => setStep(2)}>
              Continue →
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="p-7 space-y-5">
            <div>
              <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "24px", fontWeight: 700 }}>Connect a data source</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Add your first dataset to get started with AI analysis.</p>
            </div>
            <div className="space-y-2">
              {[
                { label: "Local File", desc: "CSV, Parquet, JSON", color: "text-emerald-600 bg-emerald-50" },
                { label: "SQL Database", desc: "PostgreSQL, MySQL", color: "text-sky-600 bg-sky-50" },
                { label: "MCP Plugin", desc: "Custom connector", color: "text-violet-600 bg-violet-50" },
              ].map((type) => (
                <button
                  key={type.label}
                  onClick={() => setStep(3)}
                  className="w-full flex items-center gap-3 p-3 rounded-[8px] border border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-600 hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-all text-left"
                >
                  <div className={cn("size-8 rounded-[6px] flex items-center justify-center text-sm", type.color)}>→</div>
                  <div>
                    <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{type.label}</p>
                    <p className="text-xs text-slate-400">{type.desc}</p>
                  </div>
                </button>
              ))}
            </div>
            <button onClick={() => setStep(3)} className="text-sm text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 w-full text-center">
              Skip for Now →
            </button>
          </div>
        )}

        {step === 3 && (
          <div className="p-7 space-y-5">
            <div>
              <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "24px", fontWeight: 700 }}>Invite teammates</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Collaborate with your team on Insight Platform.</p>
            </div>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Email addresses</label>
                <div className="min-h-[80px] p-2 rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 flex flex-wrap gap-1.5 items-start">
                  {emails.map((email) => (
                    <span key={email} className="flex items-center gap-1 px-2 py-0.5 bg-indigo-50 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded text-xs">
                      {email}
                      <button onClick={() => setEmails(emails.filter((e) => e !== email))} className="text-indigo-400 hover:text-indigo-600">×</button>
                    </span>
                  ))}
                  <input
                    type="email"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); addEmail(); } }}
                    placeholder="Add email and press Enter…"
                    className="flex-1 min-w-[160px] text-sm bg-transparent text-slate-800 dark:text-slate-200 placeholder:text-slate-400 outline-none"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">Role for all invitees</label>
                <select className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none">
                  <option>Viewer</option>
                  <option>Editor</option>
                  <option>Admin</option>
                </select>
              </div>
            </div>
            <div className="flex flex-col gap-2">
              <Button variant="primary" size="lg" fullWidth disabled={emails.length === 0} onClick={() => setStep(4)}>
                Send Invites
              </Button>
              <button onClick={() => setStep(4)} className="text-sm text-slate-400 hover:text-slate-600 text-center">
                Skip for Now →
              </button>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="p-7 space-y-6 text-center">
            <div className="text-5xl">🎉</div>
            <div>
              <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "36px", fontWeight: 700, lineHeight: "44px" }}>
                You're all set!
              </h1>
              <p className="text-slate-500 dark:text-slate-400 mt-2">
                Welcome to Insight Platform, {("Alex Chen").split(" ")[0]}!
              </p>
            </div>
            <div className="grid grid-cols-1 gap-3">
              {[
                { icon: <GitBranch size={18} />, title: "Create Your First Workflow", desc: "Build an AI agent pipeline", color: "text-indigo-600 bg-indigo-50 dark:bg-indigo-900/20", action: () => navigate("/workflows") },
                { icon: <BookOpen size={18} />, title: "Browse Documentation", desc: "Learn about agents and pipelines", color: "text-slate-600 bg-slate-100 dark:bg-slate-800", action: () => {} },
                { icon: <Play size={18} />, title: "Watch a 3-min Demo", desc: "See Insight Platform in action", color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20", action: () => {} },
              ].map((card) => (
                <button
                  key={card.title}
                  onClick={card.action}
                  className="flex items-center gap-4 p-4 rounded-[8px] border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors text-left"
                >
                  <div className={cn("size-10 rounded-[8px] flex items-center justify-center flex-shrink-0", card.color)}>
                    {card.icon}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{card.title}</p>
                    <p className="text-xs text-slate-400">{card.desc}</p>
                  </div>
                </button>
              ))}
            </div>
            <Button variant="primary" size="lg" fullWidth onClick={() => navigate("/dashboard")}>
              Go to Dashboard
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

