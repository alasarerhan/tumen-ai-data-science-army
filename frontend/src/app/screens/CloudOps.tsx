import React, { useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { cn } from "../lib/utils";
import {
  Cloud,
  Plus,
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  Clock,
  AlertCircle,
  Code2,
  Download,
  Eye,
} from "lucide-react";

const DEPLOYMENT_STAGES = [
  {
    name: "IaC Agent",
    icon: "🏗️",
    color: "#f97316",
    status: "success" as const,
    lastRun: "2h ago",
    toolCalls: ["terraform_init", "terraform_plan", "terraform_apply"],
    output: "3 resources created: aws_vpc, aws_subnet × 2",
    code: `resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n  tags = { Name = "insight-vpc" }\n}`,
  },
  {
    name: "Containerization Agent",
    icon: "🐳",
    color: "#06b6d4",
    status: "success" as const,
    lastRun: "1h ago",
    toolCalls: ["docker_build", "docker_tag", "docker_push"],
    output: "Image pushed: 123456789.ecr.us-east-1.amazonaws.com/insight:v3.2.1",
    code: `FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY . .\nCMD ["python", "-m", "uvicorn", "main:app"]`,
  },
  {
    name: "CI/CD Agent",
    icon: "🚀",
    color: "#8b5cf6",
    status: "running" as const,
    lastRun: "running…",
    toolCalls: ["generate_workflow", "commit_yaml", "trigger_pipeline"],
    output: "Pipeline triggered: GitHub Actions · workflow: deploy-prod",
    code: `name: Deploy to Production\non:\n  push:\n    branches: [main]\njobs:\n  deploy:\n    runs-on: ubuntu-latest`,
  },
];

const ACTIVITY_FEED = [
  { agent: "IaC Agent", tool: "terraform_apply", status: "success", time: "2h ago", input: '{ "workspace": "prod", "auto_approve": true }', output: "Apply complete! Resources: 3 added, 0 changed, 0 destroyed." },
  { agent: "Containerization", tool: "docker_push", status: "success", time: "1h ago", input: '{ "tag": "v3.2.1", "registry": "123456789.ecr.us-east-1.amazonaws.com" }', output: "Digest: sha256:abc123def456..." },
  { agent: "CI/CD Agent", tool: "generate_workflow", status: "running", time: "5m ago", input: '{ "platform": "github", "branch": "main", "env": "production" }', output: "" },
  { agent: "IaC Agent", tool: "terraform_plan", status: "success", time: "2h 5m ago", input: '{ "workspace": "prod" }', output: "Plan: 3 to add, 0 to change, 0 to destroy." },
];

const ARTIFACT_TABS = ["Terraform", "Dockerfiles", "CI/CD Pipelines"] as const;
type ArtifactTab = typeof ARTIFACT_TABS[number];

const ARTIFACTS_BY_TAB: Record<ArtifactTab, { name: string; agent: string; date: string }[]> = {
  Terraform: [
    { name: "main.tf", agent: "IaC Agent", date: "2h ago" },
    { name: "variables.tf", agent: "IaC Agent", date: "2h ago" },
    { name: "outputs.tf", agent: "IaC Agent", date: "2h ago" },
  ],
  Dockerfiles: [
    { name: "Dockerfile.prod", agent: "Containerization", date: "1h ago" },
    { name: "Dockerfile.dev", agent: "Containerization", date: "1h ago" },
  ],
  "CI/CD Pipelines": [
    { name: "deploy-prod.yml", agent: "CI/CD Agent", date: "5m ago" },
    { name: "test-suite.yml", agent: "CI/CD Agent", date: "30m ago" },
  ],
};

export default function CloudOps() {
  const [expandedStage, setExpandedStage] = useState<number | null>(null);
  const [expandedActivity, setExpandedActivity] = useState<number | null>(null);
  const [artifactTab, setArtifactTab] = useState<ArtifactTab>("Terraform");
  const [showNewDeployment, setShowNewDeployment] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);

  return (
    <AppShell>
      <div className="p-6 max-w-[1280px] mx-auto space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-slate-900 dark:text-slate-50" style={{ fontSize: "30px", fontWeight: 700, lineHeight: "38px" }}>
              CloudOps Deployments
            </h1>
            <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Infrastructure managed by AI agents.</p>
          </div>
          <Button variant="primary" size="md" leadingIcon={<Plus size={14} />} onClick={() => setShowNewDeployment(true)}>
            New Deployment
          </Button>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "IaC Resources", value: "14", badge: "Terraform", color: "text-orange-600 bg-orange-50 dark:bg-orange-900/20" },
            { label: "Container Images", value: "7", badge: "Docker", color: "text-cyan-600 bg-cyan-50 dark:bg-cyan-900/20" },
            { label: "CI/CD Pipelines", value: "5", badge: "GitHub Actions", color: "text-violet-600 bg-violet-50 dark:bg-violet-900/20" },
          ].map((card) => (
            <div key={card.label} className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">{card.label}</p>
                <span className={cn("text-[10px] px-2 py-0.5 rounded font-medium", card.color)}>{card.badge}</span>
              </div>
              <p className="text-2xl font-semibold text-slate-900 dark:text-slate-50 tabular-nums">{card.value}</p>
            </div>
          ))}
        </div>

        {/* Pipeline Stepper */}
        <div className="bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Deployment Pipeline</h2>
          </div>
          <div className="p-5">
            {/* Horizontal pipeline */}
            <div className="flex items-start gap-0">
              {DEPLOYMENT_STAGES.map((stage, idx) => (
                <React.Fragment key={stage.name}>
                  <div className="flex-1 min-w-0">
                    <div className="border border-slate-200 dark:border-slate-700 rounded-[8px] p-4 hover:border-slate-300 dark:hover:border-slate-600 transition-colors">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-lg">{stage.icon}</span>
                        <div>
                          <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{stage.name}</p>
                          <p className="text-xs text-slate-400">{stage.lastRun}</p>
                        </div>
                      </div>
                      <Badge
                        variant={stage.status === "success" ? "success" : stage.status === "running" ? "indigo" : "danger"}
                        dot
                        pulsing={stage.status === "running"}
                        size="sm"
                      >
                        {stage.status.charAt(0).toUpperCase() + stage.status.slice(1)}
                      </Badge>
                      <button
                        onClick={() => setExpandedStage(expandedStage === idx ? null : idx)}
                        className="mt-2 text-xs text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
                      >
                        View Logs {expandedStage === idx ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
                      </button>
                    </div>
                    {expandedStage === idx && (
                      <div className="mt-2 p-3 rounded-[6px] bg-slate-50 dark:bg-slate-800 border border-slate-100 dark:border-slate-700 text-xs space-y-2">
                        <div className="flex flex-wrap gap-1">
                          {stage.toolCalls.map((tc) => (
                            <code key={tc} className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded text-slate-600 dark:text-slate-300">{tc}</code>
                          ))}
                        </div>
                        <p className="text-slate-500">{stage.output}</p>
                        <pre className="bg-slate-900 text-slate-300 p-2 rounded text-[10px] overflow-x-auto font-mono whitespace-pre">{stage.code}</pre>
                      </div>
                    )}
                  </div>
                  {idx < DEPLOYMENT_STAGES.length - 1 && (
                    <div className="flex items-center px-2 pt-6">
                      <div className="w-6 h-px bg-slate-300 dark:bg-slate-600" />
                      <ChevronRight size={12} className="text-slate-400 -ml-1" />
                    </div>
                  )}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom 2-col */}
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
          {/* Activity Feed */}
          <div className="lg:col-span-3 bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Agent Activity</h2>
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {ACTIVITY_FEED.map((item, idx) => (
                <div key={idx}>
                  <button
                    onClick={() => setExpandedActivity(expandedActivity === idx ? null : idx)}
                    className="w-full flex items-center gap-3 px-5 py-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors text-left"
                  >
                    <span className="text-[10px] px-1.5 py-0.5 rounded font-medium flex-shrink-0" style={{
                      backgroundColor: item.agent === "IaC Agent" ? "#f9731620" : item.agent === "Containerization" ? "#06b6d420" : "#8b5cf620",
                      color: item.agent === "IaC Agent" ? "#f97316" : item.agent === "Containerization" ? "#06b6d4" : "#8b5cf6",
                    }}>
                      {item.agent}
                    </span>
                    <code className="text-xs font-mono text-slate-600 dark:text-slate-300 flex-1 text-left">{item.tool}</code>
                    {item.status === "success" ? (
                      <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" />
                    ) : item.status === "running" ? (
                      <div className="size-3.5 rounded-full border-2 border-indigo-500 border-t-transparent animate-spin flex-shrink-0" />
                    ) : (
                      <AlertCircle size={14} className="text-red-500 flex-shrink-0" />
                    )}
                    <span className="text-xs text-slate-400 flex-shrink-0">{item.time}</span>
                  </button>
                  {expandedActivity === idx && (
                    <div className="px-5 pb-3 ml-3 space-y-2 text-xs">
                      <div>
                        <p className="text-slate-400 mb-1">Input</p>
                        <code className="block bg-slate-50 dark:bg-slate-800 px-2 py-1.5 rounded text-slate-600 dark:text-slate-300">{item.input}</code>
                      </div>
                      {item.output && (
                        <div>
                          <p className="text-slate-400 mb-1">Output</p>
                          <code className="block bg-slate-50 dark:bg-slate-800 px-2 py-1.5 rounded text-slate-600 dark:text-slate-300">{item.output}</code>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Artifacts */}
          <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-[8px] border border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 dark:border-slate-800">
              <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">Generated Artifacts</h2>
            </div>
            {/* Tabs */}
            <div className="flex border-b border-slate-100 dark:border-slate-800 px-3">
              {ARTIFACT_TABS.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setArtifactTab(tab)}
                  className={cn(
                    "px-3 py-2.5 text-xs font-medium border-b-2 -mb-px transition-colors",
                    artifactTab === tab
                      ? "border-indigo-600 text-indigo-600 dark:text-indigo-400"
                      : "border-transparent text-slate-500 hover:text-slate-700"
                  )}
                >
                  {tab}
                </button>
              ))}
            </div>
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
              {ARTIFACTS_BY_TAB[artifactTab].map((art) => (
                <div key={art.name} className="flex items-center gap-3 px-5 py-3">
                  <Code2 size={14} className="text-slate-400 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-mono text-slate-700 dark:text-slate-200">{art.name}</p>
                    <p className="text-[10px] text-slate-400">{art.agent} · {art.date}</p>
                  </div>
                  <div className="flex gap-1">
                    <button className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="View file">
                      <Eye size={12} />
                    </button>
                    <button className="p-1 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800" aria-label="Download file">
                      <Download size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* New Deployment Modal */}
      {showNewDeployment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowNewDeployment(false)} />
          <div className="relative bg-white dark:bg-slate-900 rounded-[12px] shadow-xl w-full max-w-[560px] mx-4 overflow-hidden" role="dialog" aria-modal="true" aria-label="New Deployment">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700">
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">Configure New Deployment</h2>
              {/* Step indicator */}
              <div className="flex gap-2 mt-3">
                {["IaC Config", "Container Config", "CI/CD Config"].map((step, idx) => (
                  <div key={step} className="flex items-center gap-2">
                    <div className={cn(
                      "size-5 rounded-full text-[10px] font-semibold flex items-center justify-center",
                      wizardStep > idx + 1 ? "bg-emerald-500 text-white" : wizardStep === idx + 1 ? "bg-indigo-600 text-white" : "bg-slate-200 dark:bg-slate-700 text-slate-500"
                    )}>
                      {wizardStep > idx + 1 ? "✓" : idx + 1}
                    </div>
                    <span className={cn("text-xs", wizardStep === idx + 1 ? "text-slate-800 dark:text-slate-200 font-medium" : "text-slate-400")}>{step}</span>
                    {idx < 2 && <div className="w-4 h-px bg-slate-200 dark:bg-slate-700" />}
                  </div>
                ))}
              </div>
            </div>
            <div className="px-6 py-5 space-y-4">
              {wizardStep === 1 && (
                <>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Cloud Provider</label>
                    <select className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                      <option>AWS</option>
                      <option>GCP</option>
                      <option>Azure</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Resource Type</label>
                    <select className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                      <option>ECS Cluster</option>
                      <option>Lambda</option>
                      <option>EC2 Auto Scaling</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Region</label>
                    <input defaultValue="us-east-1" className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                </>
              )}
              {wizardStep === 2 && (
                <>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Base Image</label>
                    <input defaultValue="python:3.11-slim" className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Registry URL</label>
                    <input defaultValue="123456789.dkr.ecr.us-east-1.amazonaws.com" className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                </>
              )}
              {wizardStep === 3 && (
                <>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Platform</label>
                    <select className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                      <option>GitHub Actions</option>
                      <option>GitLab CI</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">Branch Trigger</label>
                    <input defaultValue="main" className="w-full h-9 px-3 text-sm rounded-[6px] border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
                  </div>
                </>
              )}
            </div>
            <div className="px-6 py-4 border-t border-slate-200 dark:border-slate-700 flex justify-between">
              <Button variant="ghost" size="md" onClick={() => wizardStep > 1 ? setWizardStep(wizardStep - 1) : setShowNewDeployment(false)}>
                {wizardStep > 1 ? "Back" : "Cancel"}
              </Button>
              <Button variant="primary" size="md" onClick={() => wizardStep < 3 ? setWizardStep(wizardStep + 1) : setShowNewDeployment(false)}>
                {wizardStep < 3 ? "Next →" : "Deploy"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}

