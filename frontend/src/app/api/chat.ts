import { BASE_URL, apiDelete, apiGet, apiPost, qs, withCsrfHeader } from "./client";
import { readSseStream } from "./sse";

export interface ChatSessionDto {
  id: string;
  tenant_id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  status: "active" | "archived";
  created_at: string | null;
  updated_at: string | null;
}

export interface ChartArtifact {
  type: "chart";
  chart_type: "line" | "bar" | "sankey" | "network";
  series?: Array<{ name: string; data: number[] }>;
  categories?: string[];
  nodes?: Array<{ name: string; value?: number; category?: string }>;
  links?: Array<{ source: string; target: string; value?: number }>;
  meta?: Record<string, unknown>;
}

export interface TableArtifact {
  type: "table";
  columns: string[];
  records: Array<Record<string, unknown>>;
}

export interface CodeArtifact {
  type: "code";
  language: string;
  code: string;
}

export interface ReportArtifact {
  type: "report";
  title: string;
  content: string;
}

export interface WorkflowDesignArtifact {
  type: "workflow_design";
  workflow_spec: {
    name: string;
    description?: string;
    steps: Array<{
      id: string;
      agent: string;
      instruction: string;
      depends_on?: string[];
      fallbacks?: string[];
    }>;
    schedule?: {
      cron?: string;
      natural_language?: string;
      timezone?: string;
    };
    hitl_config?: {
      approval_gates: string[];
      confidence_threshold: number;
    };
  };
}

export type ArtifactDto = ChartArtifact | TableArtifact | CodeArtifact | ReportArtifact | WorkflowDesignArtifact;

export interface ChatMessageDto {
  id: string;
  session_id: string;
  role: "system" | "user" | "assistant";
  content: string;
  artifacts: ArtifactDto[];
  created_at: string | null;
}

export interface ChatUploadDto {
  id: string;
  session_id: string;
  filename: string;
  content_type: string | null;
  size_bytes: number;
  storage_uri: string;
  created_at: string | null;
}

export interface ChatStreamState {
  messageId: string | null;
  content: string;
  isComplete: boolean;
  error: string | null;
}

export const createChatSession = (body: { workspace_id: string; title: string }) =>
  apiPost<ChatSessionDto>("/v1/chat/sessions", body);

export const listChatSessions = (workspace_id: string) =>
  apiGet<{ items: ChatSessionDto[] }>(`/v1/chat/sessions${qs({ workspace_id })}`);

export const getChatSession = (session_id: string, workspace_id: string) =>
  apiGet<ChatSessionDto>(`/v1/chat/sessions/${session_id}${qs({ workspace_id })}`);

export const archiveChatSession = (session_id: string, workspace_id: string) =>
  apiDelete<ChatSessionDto>(`/v1/chat/sessions/${session_id}${qs({ workspace_id })}`);

export const listChatMessages = (session_id: string, workspace_id: string) =>
  apiGet<{ items: ChatMessageDto[] }>(`/v1/chat/sessions/${session_id}/messages${qs({ workspace_id })}`);

export const sendChatMessage = (session_id: string, body: { workspace_id: string; content: string }) =>
  apiPost<ChatMessageDto>(`/v1/chat/sessions/${session_id}/messages`, body);

export interface StreamChatHandlers {
  onDelta: (delta: string, messageId: string) => void;
  onMessage: (message: ChatMessageDto) => void;
  onDone?: (messageId: string) => void;
  onError?: (error: Error, messageId: string | null) => void;
}

export async function streamChatMessage(
  session_id: string,
  body: { workspace_id: string; content: string },
  handlers: StreamChatHandlers,
): Promise<void> {
  const headers = await withCsrfHeader({
    "Content-Type": "application/json",
  });
  const res = await fetch(`${BASE_URL}/v1/chat/sessions/${session_id}/messages/stream`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    handlers.onError?.(new Error(`Streaming failed: HTTP ${res.status}`), null);
    return;
  }

  type StreamEvent = {
    type: "progress" | "delta" | "message" | "done" | "error";
    delta?: string;
    message?: ChatMessageDto;
    message_id?: string;
    error?: string;
  };

  let currentMessageId: string | null = null;

  const parsePayload = (raw: string): StreamEvent => {
    try {
      return JSON.parse(raw) as StreamEvent;
    } catch {
      return { type: "error", error: "Failed to parse event" };
    }
  };

  try {
    await readSseStream({
      stream: res.body,
      parse: parsePayload,
      onEvent: (payload) => {
        if (payload.message_id) {
          currentMessageId = payload.message_id;
        }

        if (payload.type === "delta" && payload.delta) {
          handlers.onDelta(payload.delta, currentMessageId || "");
          return;
        }
        if (payload.type === "message" && payload.message) {
          handlers.onMessage(payload.message);
          return;
        }
        if (payload.type === "error") {
          handlers.onError?.(new Error(payload.error ?? "Unknown stream error"), currentMessageId);
          return;
        }
        if (payload.type === "done") {
          handlers.onDone?.(currentMessageId || "");
        }
      },
    });
  } catch (err: unknown) {
    handlers.onError?.(err instanceof Error ? err : new Error(String(err)), currentMessageId);
  }
}

export const uploadChatFile = async (session_id: string, workspace_id: string, file: File) => {
  const form = new FormData();
  form.append("workspace_id", workspace_id);
  form.append("file", file);
  return apiPost<ChatUploadDto>(`/v1/chat/sessions/${session_id}/uploads`, form);
};

export const listChatUploads = (session_id: string, workspace_id: string) =>
  apiGet<{ items: ChatUploadDto[] }>(`/v1/chat/sessions/${session_id}/uploads${qs({ workspace_id })}`);
