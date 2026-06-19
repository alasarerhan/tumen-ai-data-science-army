import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { Activity, AlertTriangle, CheckCircle2, ExternalLink, FileCode2, Table2, BarChart3, FileText, GitBranch, Shield } from "lucide-react";
import type { ArtifactDto, ChartArtifact } from "../../api/chat";
import type { PlatformActionPlan, PlatformQueryResultArtifact } from "../../api/controlPlane";
import { SankeyChart } from "../charts/sankey-chart";
import { NetworkChart } from "../charts/network-chart";
import { TrendChart } from "../charts/trend-chart";
import { Button } from "../ui/button";

const SANITIZE_SCHEMA = {
  tagNames: [
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'p', 'div', 'span', 'br', 'hr',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'code',
    'strong', 'em', 'b', 'i', 'u', 's',
    'a',
    'table', 'thead', 'tbody', 'tr', 'th', 'td',
    'img',
  ],
  attributes: {
    a: ['href', 'title'],
    img: ['src', 'alt', 'title'],
    code: ['className'],
    pre: ['className'],
  },
  protocols: {
    href: ['http', 'https'],
    src: ['http', 'https', 'data'],
  },
};

interface ArtifactCardProps {
  artifact: ArtifactDto;
  onPlatformActionConfirm?: (actionPlan: PlatformActionPlan) => void;
}

function renderChartArtifact(artifact: ChartArtifact) {
  if (artifact.chart_type === "sankey") {
    return <SankeyChart nodes={artifact.nodes ?? []} links={artifact.links ?? []} />;
  }
  if (artifact.chart_type === "network") {
    return <NetworkChart nodes={artifact.nodes ?? []} links={artifact.links ?? []} />;
  }
  return <TrendChart categories={artifact.categories} series={artifact.series ?? []} />;
}

function renderPlatformQueryResult(
  artifact: PlatformQueryResultArtifact,
  onPlatformActionConfirm?: (actionPlan: PlatformActionPlan) => void,
) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-600">
        <Activity size={14} /> Platform Query
      </div>
      <p className="text-sm text-slate-800">{artifact.summary}</p>
      <div className="mt-3 space-y-3">
        {artifact.sections.map((section) => (
          <div key={section.resource_key} className="border-t border-slate-100 pt-3">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                {section.status === "ok" ? (
                  <CheckCircle2 size={14} className="text-emerald-600" />
                ) : (
                  <AlertTriangle size={14} className="text-amber-600" />
                )}
                <p className="text-xs font-semibold text-slate-700">{section.label}</p>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase text-slate-500">
                  {section.status}
                </span>
              </div>
              {section.links[0] ? (
                <a className="flex items-center gap-1 text-xs text-indigo-600 hover:underline" href={section.links[0].href}>
                  {section.links[0].label}
                  <ExternalLink size={11} />
                </a>
              ) : null}
            </div>
            {section.message ? <p className="text-xs text-slate-500">{section.message}</p> : null}
            {Object.keys(section.metrics).length > 0 ? (
              <div className="mb-2 grid grid-cols-2 gap-2 md:grid-cols-3">
                {Object.entries(section.metrics).map(([key, value]) => (
                  <div key={key} className="rounded border border-slate-200 px-2 py-1">
                    <p className="text-[10px] uppercase text-slate-400">{key}</p>
                    <p className="text-sm font-semibold text-slate-800">{String(value)}</p>
                  </div>
                ))}
              </div>
            ) : null}
            {section.records.length > 0 && section.columns.length > 0 ? (
              <div className="overflow-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {section.columns.slice(0, 6).map((column) => (
                        <th key={column} className="border-b border-slate-200 px-2 py-1 text-left font-semibold text-slate-600">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {section.records.slice(0, 5).map((record, idx) => (
                      <tr key={idx}>
                        {section.columns.slice(0, 6).map((column) => (
                          <td key={column} className="border-b border-slate-100 px-2 py-1 text-slate-700">
                            {formatCell(record[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
            {(section.relationships ?? []).length > 0 ? (
              <div className="mt-2 rounded border border-slate-200 bg-slate-50 p-2">
                <p className="mb-1 text-[10px] font-semibold uppercase text-slate-500">Relationships</p>
                <div className="space-y-1">
                  {(section.relationships ?? []).slice(0, 6).map((relationship, idx) => (
                    <div key={`${relationship.relationship_type}-${idx}`} className="flex flex-wrap items-center gap-1 text-xs text-slate-600">
                      <span className="font-medium text-slate-700">{relationship.source.label}</span>
                      <span>-&gt;</span>
                      <span className="rounded bg-white px-1 py-0.5 text-[10px] uppercase text-slate-500">
                        {relationship.relationship_type}
                      </span>
                      <span>-&gt;</span>
                      <span className="font-medium text-slate-700">{relationship.target.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <p className="mt-2 flex items-center gap-1 text-[10px] text-slate-400">
              <Shield size={10} />
              {section.provenance.resolver} at {section.provenance.generated_at}
              {section.provenance.redactions.length > 0 ? `; redacted: ${section.provenance.redactions.join(", ")}` : ""}
            </p>
          </div>
        ))}
      </div>
      {artifact.action_plan ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-800">{artifact.action_plan.summary}</p>
          {artifact.action_plan.denial_reason ? (
            <p className="mt-1 text-xs text-amber-700">{artifact.action_plan.denial_reason}</p>
          ) : null}
          {artifact.action_plan.missing_arguments.length > 0 ? (
            <p className="mt-1 text-xs text-amber-700">
              Missing: {artifact.action_plan.missing_arguments.join(", ")}
            </p>
          ) : null}
          <Button
            className="mt-2"
            size="xs"
            variant="secondary"
            disabled={!artifact.action_plan.allowed || artifact.action_plan.missing_arguments.length > 0}
            onClick={() => onPlatformActionConfirm?.(artifact.action_plan!)}
          >
            Confirm Action
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ArtifactCard({ artifact, onPlatformActionConfirm }: ArtifactCardProps) {
  if (artifact.type === "platform_query_result") {
    return renderPlatformQueryResult(artifact, onPlatformActionConfirm);
  }

  if (artifact.type === "table") {
    return (
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-600">
          <Table2 size={14} /> Table
        </div>
        <div className="overflow-auto">
          <table className="w-full text-xs">
            <thead>
              <tr>
                {artifact.columns.map((column) => (
                  <th key={column} className="border-b border-slate-200 px-2 py-1 text-left font-semibold text-slate-600">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {artifact.records.slice(0, 8).map((record, idx) => (
                <tr key={idx}>
                  {artifact.columns.map((column) => (
                    <td key={column} className="border-b border-slate-100 px-2 py-1 text-slate-700">
                      {String(record[column] ?? "")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (artifact.type === "chart") {
    return (
      <div className="rounded-md border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-600">
          <BarChart3 size={14} /> Chart ({artifact.chart_type})
        </div>
        {renderChartArtifact(artifact)}
      </div>
    );
  }

  if (artifact.type === "code") {
    return (
      <div className="overflow-hidden rounded-md border border-slate-200">
        <div className="flex items-center gap-2 border-b border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300">
          <FileCode2 size={14} /> {artifact.language}
        </div>
        <pre className="max-h-80 overflow-auto bg-slate-950 p-3 text-xs text-slate-100">
          <code>{artifact.code}</code>
        </pre>
      </div>
    );
  }

  if (artifact.type === "workflow_design") {
    return (
      <div className="rounded-md border border-indigo-200 bg-indigo-50 p-3">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-indigo-700">
          <GitBranch size={14} /> Workflow Design
        </div>
        <p className="text-sm font-medium text-slate-800">{artifact.workflow_spec.name}</p>
        {artifact.workflow_spec.description ? (
          <p className="mt-1 text-xs text-slate-600">{artifact.workflow_spec.description}</p>
        ) : null}
        <p className="mt-2 text-xs text-slate-500">{artifact.workflow_spec.steps.length} planned steps</p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-slate-200 bg-white p-3">
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-600">
        <FileText size={14} /> {artifact.title}
      </div>
      <div className="prose prose-slate max-w-none text-sm">
        <ReactMarkdown 
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}
        >
          {artifact.content}
        </ReactMarkdown>
      </div>
    </div>
  );
}

