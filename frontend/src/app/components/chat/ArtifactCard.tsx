import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { FileCode2, Table2, BarChart3, FileText, Copy, Check } from "lucide-react";
import { toast } from "sonner";
import type { ArtifactDto, ChartArtifact } from "../../api/chat";
import { SankeyChart } from "../charts/sankey-chart";
import { NetworkChart } from "../charts/network-chart";
import { TrendChart } from "../charts/trend-chart";

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

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (text: string) => {
    if (!navigator.clipboard) {
      toast.error("Clipboard API not available");
      return;
    }
    void navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

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
        <div className="flex items-center justify-between border-b border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <FileCode2 size={14} /> {artifact.language}
          </div>
          <button
            type="button"
            onClick={() => handleCopy(artifact.code)}
            className="rounded p-1 hover:bg-slate-800 transition-colors"
            aria-label="Copy code"
          >
            {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
          </button>
        </div>
        <pre className="max-h-80 overflow-auto bg-slate-950 p-3 text-xs text-slate-100">
          <code>{artifact.code}</code>
        </pre>
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

