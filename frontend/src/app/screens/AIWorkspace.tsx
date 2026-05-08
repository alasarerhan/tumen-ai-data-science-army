import React, { useEffect, useMemo, useRef, useState } from "react";
import { Plus, Send, Loader2 } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import {
  streamChatMessage,
  type ChatMessageDto,
  type WorkflowDesignArtifact,
} from "../api/chat";
import { triggerScheduledWorkflow } from "../api/scheduler";
import { ChatMessage } from "../components/chat/ChatMessage";
import { FileDropZone } from "../components/chat/FileDropZone";
import {
  useChatMessages,
  useChatSessions,
  useChatUploads,
  useCreateChatSession,
  useUploadChatFiles,
} from "../hooks/useChatWorkspace";
import { useCreateWorkflow, usePublishWorkflow } from "../hooks/useWorkflows";
import { useWorkflowChainRules } from "../hooks/useWorkflowChainRules";
import { inspectWorkflowSpec } from "../utils/workflowChainValidator";

function buildLocalMessage(partial: Partial<ChatMessageDto> & Pick<ChatMessageDto, "id" | "role" | "content">): ChatMessageDto {
  return {
    id: partial.id,
    role: partial.role,
    content: partial.content,
    session_id: partial.session_id ?? "local",
    artifacts: partial.artifacts ?? [],
    created_at: partial.created_at ?? new Date().toISOString(),
  };
}

export default function AIWorkspace() {
  const { workspaceId } = useAuth();
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageDto[]>([]);
  const [prompt, setPrompt] = useState("");
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [workspaceNotice, setWorkspaceNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const feedRef = useRef<HTMLDivElement | null>(null);

  const sessionsQuery = useChatSessions(workspaceId);
  const messagesQuery = useChatMessages(activeSessionId, workspaceId);
  const uploadsQuery = useChatUploads(activeSessionId, workspaceId);
  const createSessionMutation = useCreateChatSession(workspaceId);
  const uploadFilesMutation = useUploadChatFiles(activeSessionId, workspaceId);
  const createWorkflowMutation = useCreateWorkflow();
  const publishWorkflowMutation = usePublishWorkflow();
  const workflowChainRulesQuery = useWorkflowChainRules(workspaceId);

  const sessions = sessionsQuery.data?.items ?? [];
  const uploads = uploadsQuery.data?.items ?? [];
  const loadingSessions = sessionsQuery.isLoading;
  const loadingMessages = messagesQuery.isLoading;
  const uploading = uploadFilesMutation.isPending;

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [sessions, activeSessionId],
  );

  useEffect(() => {
    if (sessionsQuery.error) {
      setSessionError(
        sessionsQuery.error instanceof Error ? sessionsQuery.error.message : "Failed to load sessions",
      );
      return;
    }
    setSessionError(null);
  }, [sessionsQuery.error]);

  useEffect(() => {
    if (!workspaceId || sessionsQuery.isLoading || createSessionMutation.isPending) {
      return;
    }
    if (sessions.length > 0) {
      setActiveSessionId((current) => current ?? sessions[0]?.id ?? null);
      return;
    }
    void createSessionMutation.mutateAsync("New chat").then((created) => {
      setActiveSessionId(created.id);
    }).catch((err: unknown) => {
      setSessionError(err instanceof Error ? err.message : "Failed to create session");
    });
  }, [workspaceId, sessions, sessionsQuery.isLoading, createSessionMutation]);

  useEffect(() => {
    if (!messagesQuery.data) {
      if (!messagesQuery.isLoading) {
        setMessages([]);
      }
      return;
    }
    setMessages(messagesQuery.data.items);
  }, [messagesQuery.data, messagesQuery.isLoading]);

  useEffect(() => {
    if (!feedRef.current) return;
    feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [messages]);

  const handleCreateSession = async () => {
    if (!workspaceId) return;
    const title = `Chat ${sessions.length + 1}`;
    const session = await createSessionMutation.mutateAsync(title);
    setActiveSessionId(session.id);
    setMessages([]);
  };

  const handleUpload = async (files: File[]) => {
    if (!workspaceId || !activeSessionId || files.length === 0) return;
    try {
      await uploadFilesMutation.mutateAsync(files);
    } catch (err: unknown) {
      setSessionError(err instanceof Error ? err.message : "Failed to upload file");
    }
  };

  const handleSend = async () => {
    if (!workspaceId || !activeSessionId || sending) return;
    const content = prompt.trim();
    if (!content) return;

    setWorkspaceNotice(null);
    setPrompt("");
    setSending(true);

    const userMsg = buildLocalMessage({ id: `u-${Date.now()}`, role: "user", content, session_id: activeSessionId });
    const draftId = `a-draft-${Date.now()}`;
    const draft = buildLocalMessage({ id: draftId, role: "assistant", content: "", session_id: activeSessionId });

    setMessages((prev) => [...prev, userMsg, draft]);

    await streamChatMessage(
      activeSessionId,
      { workspace_id: workspaceId, content },
      {
        onDelta: (delta) => {
          setMessages((prev) =>
            prev.map((msg) => (msg.id === draftId ? { ...msg, content: `${msg.content}${delta}` } : msg)),
          );
        },
        onMessage: (message) => {
          setMessages((prev) => prev.map((msg) => (msg.id === draftId ? message : msg)));
        },
        onDone: () => {
          setSending(false);
          void sessionsQuery.refetch();
          void messagesQuery.refetch();
        },
        onError: () => {
          setSending(false);
          setMessages((prev) => prev.filter((msg) => msg.id !== draftId));
        },
      },
    );
  };

  const removeWorkflowArtifact = (artifactId: string) => {
    const marker = "-artifact-";
    const markerIndex = artifactId.lastIndexOf(marker);
    if (markerIndex === -1) return;
    const messageId = artifactId.slice(0, markerIndex);
    const artifactIndex = Number(artifactId.slice(markerIndex + marker.length));
    if (Number.isNaN(artifactIndex)) return;

    setMessages((prev) =>
      prev.map((message) => {
        if (message.id !== messageId) {
          return message;
        }
        return {
          ...message,
          artifacts: message.artifacts.filter((_, index) => index !== artifactIndex),
        };
      }),
    );
  };

  const normalizeWorkflowSpec = (workflowSpec: WorkflowDesignArtifact["workflow_spec"]) => ({
    name: workflowSpec.name,
    description: workflowSpec.description,
    schedule: workflowSpec.schedule,
    hitl_config: workflowSpec.hitl_config,
    steps: workflowSpec.steps.map((step) => ({
      id: step.id,
      tool: step.agent,
      agent: step.agent,
      instruction: step.instruction,
      depends_on: step.depends_on ?? [],
      fallbacks: step.fallbacks ?? [],
    })),
  });

  const handleWorkflowApprove = async (
    artifactId: string,
    workflowSpec: WorkflowDesignArtifact["workflow_spec"],
  ) => {
    if (!workspaceId || !activeSessionId) return;
    setSessionError(null);
    setWorkspaceNotice(null);

    try {
      const normalizedSpec = normalizeWorkflowSpec(workflowSpec);
      const validation = inspectWorkflowSpec(normalizedSpec, workflowChainRulesQuery.data?.ruleset);
      if (validation.errors.length > 0) {
        setSessionError(validation.errors.map((issue) => issue.message).join(" "));
        return;
      }

      const created = await createWorkflowMutation.mutateAsync({
        workspace_id: workspaceId,
        name: workflowSpec.name,
        spec: normalizedSpec,
        publish: false,
      });

      let notice = `Workflow "${workflowSpec.name}" saved as draft.`;

      try {
        await publishWorkflowMutation.mutateAsync({ id: created.id, workspace_id: workspaceId });
        notice = `Workflow "${workflowSpec.name}" published.`;

        try {
          const run = await triggerScheduledWorkflow(created.id, workspaceId);
          notice = `Workflow "${workflowSpec.name}" published and triggered. Run: ${run.flow_run_id}.`;
        } catch (triggerError: unknown) {
          notice = triggerError instanceof Error
            ? `Workflow "${workflowSpec.name}" published, but run trigger failed: ${triggerError.message}`
            : `Workflow "${workflowSpec.name}" published, but run trigger failed.`;
        }
      } catch (publishError: unknown) {
        notice = publishError instanceof Error
          ? `Workflow saved as draft. Publish requires additional permissions or failed: ${publishError.message}`
          : "Workflow saved as draft. Publish requires additional permissions.";
      }

      removeWorkflowArtifact(artifactId);
      if (validation.warnings.length > 0) {
        notice = `${notice} Warnings: ${validation.warnings.map((issue) => issue.message).join(" ")}`;
      }
      setWorkspaceNotice(notice);
    } catch (err: unknown) {
      setSessionError(err instanceof Error ? err.message : "Failed to approve workflow");
    }
  };

  const handleWorkflowModify = async (artifactId: string, feedback: string) => {
    if (!workspaceId || !activeSessionId) return;
    setWorkspaceNotice("Workflow feedback copied into the prompt editor. Send it to generate a revised draft.");
    setPrompt(`Revise the workflow proposal. Feedback: ${feedback}`);
  };

  const handleWorkflowCancel = async (artifactId: string) => {
    removeWorkflowArtifact(artifactId);
    setWorkspaceNotice("Workflow proposal dismissed.");
  };

  return (
    <AppShell>
      <div className="grid h-full grid-cols-12 gap-0">
        <aside className="col-span-3 border-r border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-3">
            <h2 className="text-sm font-semibold text-slate-800">AI Workspace</h2>
            <Button variant="secondary" size="xs" leadingIcon={<Plus size={13} />} onClick={handleCreateSession}>
              New
            </Button>
          </div>

          <div className="space-y-4 p-3">
            <AsyncState
              isLoading={loadingSessions}
              error={sessionError}
              isEmpty={!loadingSessions && sessions.length === 0}
              emptyTitle="No sessions"
              emptyDescription="Start a chat to work with your data."
              onRetry={() => {
                void sessionsQuery.refetch();
              }}
              className="py-4"
            >
              <div className="space-y-1">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    type="button"
                    onClick={() => setActiveSessionId(session.id)}
                    className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                      activeSessionId === session.id
                        ? "bg-indigo-50 text-indigo-700"
                        : "text-slate-600 hover:bg-slate-100"
                    }`}
                  >
                    <p className="truncate font-medium">{session.title}</p>
                    <p className="truncate text-xs text-slate-400">{session.updated_at ?? session.created_at}</p>
                  </button>
                ))}
              </div>
            </AsyncState>

            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Uploads</p>
              <FileDropZone onFiles={handleUpload} disabled={!activeSessionId || uploading} />
              {uploads.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {uploads.map((upload) => (
                    <li key={upload.id} className="truncate rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">
                      {upload.filename}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </div>
        </aside>

        <section className="col-span-9 flex h-full flex-col">
          <div className="border-b border-slate-200 px-4 py-3">
            <h1 className="text-sm font-semibold text-slate-800">{activeSession?.title ?? "Session"}</h1>
            <p className="text-xs text-slate-400">Table, chart, code, and report artifacts render inline.</p>
            {workspaceNotice ? (
              <p className="mt-2 text-xs text-indigo-600">{workspaceNotice}</p>
            ) : null}
            {sessionError ? (
              <p className="mt-2 text-xs text-rose-600">{sessionError}</p>
            ) : null}
          </div>

          <div ref={feedRef} className="flex-1 space-y-3 overflow-auto bg-slate-50 p-4">
            <AsyncState
              isLoading={loadingMessages}
              isEmpty={!loadingMessages && messages.length === 0}
              emptyTitle="Ask a question"
              emptyDescription="Try: summarize uploaded data and propose next actions."
              className="flex h-full items-center justify-center"
            >
            {messages.map((message) => (
                <ChatMessage 
                  key={message.id} 
                  message={message} 
                  onWorkflowApprove={handleWorkflowApprove}
                  onWorkflowModify={handleWorkflowModify}
                  onWorkflowCancel={handleWorkflowCancel}
                />
              ))}
            </AsyncState>
          </div>

          <div className="border-t border-slate-200 bg-white p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                className="min-h-[72px] flex-1 resize-none rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                placeholder="Ask AI to analyze, forecast, or generate a report..."
              />
              <Button
                variant="primary"
                size="md"
                disabled={!prompt.trim() || sending || !activeSessionId}
                onClick={() => {
                  void handleSend();
                }}
                leadingIcon={sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              >
                Send
              </Button>
            </div>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

