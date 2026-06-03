import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";
import { cn } from "../../lib/utils";
import type { ChatMessageDto } from "../../api/chat";
import { ArtifactCard } from "./ArtifactCard";
import { WorkflowDesignMessage } from "./WorkflowDesignMessage";

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

interface ChatMessageProps {
  message: ChatMessageDto;
  onWorkflowApprove?: (artifactId: string, workflowSpec: Extract<ChatMessageDto["artifacts"][number], { type: "workflow_design" }>["workflow_spec"]) => void;
  onWorkflowModify?: (artifactId: string, feedback: string) => void;
  onWorkflowCancel?: (artifactId: string) => void;
}

export function ChatMessage({ 
  message, 
  onWorkflowApprove, 
  onWorkflowModify, 
  onWorkflowCancel 
}: ChatMessageProps) {
  const isAssistant = message.role === "assistant";

  const renderArtifact = (artifact: ChatMessageDto["artifacts"][0], idx: number) => {
    if (artifact.type === "workflow_design") {
      return (
        <WorkflowDesignMessage
          key={`${message.id}-artifact-${idx}`}
          workflowSpec={artifact.workflow_spec}
          onApprove={() => onWorkflowApprove?.(`${message.id}-artifact-${idx}`, artifact.workflow_spec)}
          onModify={(feedback) => onWorkflowModify?.(`${message.id}-artifact-${idx}`, feedback)}
          onCancel={() => onWorkflowCancel?.(`${message.id}-artifact-${idx}`)}
        />
      );
    }
    return <ArtifactCard key={`${message.id}-artifact-${idx}`} artifact={artifact} />;
  };

  return (
    <div className={cn("flex w-full", isAssistant ? "justify-start" : "justify-end")}> 
      <div
        className={cn(
          "max-w-[90%] rounded-lg border px-3 py-2",
          isAssistant
            ? "border-slate-200 bg-white text-slate-800"
            : "border-indigo-200 bg-indigo-50 text-indigo-900",
        )}
      >
        <p className="mb-1 text-[11px] uppercase tracking-wide text-slate-400">{message.role}</p>
        <div className="prose prose-sm max-w-none prose-p:my-1">
          <ReactMarkdown 
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.artifacts.length > 0 ? (
          <div className="mt-3 space-y-2">
            {message.artifacts.map((artifact, idx) => renderArtifact(artifact, idx))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

