import React, { useEffect, useMemo, useRef, useState } from "react";
import { Plus, Send, Loader2 } from "lucide-react";
import { AppShell } from "../components/layout/AppShell";
import { Button } from "../components/ui/button";
import { AsyncState } from "../components/ui/async-state";
import { useAuth } from "../context/AuthContext";
import {
  createChatSession,
  listChatSessions,
  listChatMessages,
  listChatUploads,
  streamChatMessage,
  uploadChatFile,
  type ChatMessageDto,
  type ChatSessionDto,
  type ChatUploadDto,
} from "../api/chat";
import { ChatMessage } from "../components/chat/ChatMessage";
import { FileDropZone } from "../components/chat/FileDropZone";

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
  const [sessions, setSessions] = useState<ChatSessionDto[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessageDto[]>([]);
  const [uploads, setUploads] = useState<ChatUploadDto[]>([]);
  const [prompt, setPrompt] = useState("");
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const feedRef = useRef<HTMLDivElement | null>(null);

  const activeSession = useMemo(
    () => sessions.find((session) => session.id === activeSessionId) ?? null,
    [sessions, activeSessionId],
  );

  const loadSessions = async () => {
    if (!workspaceId) return;
    setLoadingSessions(true);
    setSessionError(null);
    try {
      const response = await listChatSessions(workspaceId);
      let items = response.items;
      if (items.length === 0) {
        const created = await createChatSession({ workspace_id: workspaceId, title: "New chat" });
        items = [created];
      }
      setSessions(items);
      setActiveSessionId((current) => current ?? items[0]?.id ?? null);
    } catch (err: unknown) {
      setSessionError(err instanceof Error ? err.message : "Failed to load sessions");
    } finally {
      setLoadingSessions(false);
    }
  };

  const loadConversation = async (sessionId: string) => {
    if (!workspaceId) return;
    setLoadingMessages(true);
    try {
      const [messageRes, uploadRes] = await Promise.all([
        listChatMessages(sessionId, workspaceId),
        listChatUploads(sessionId, workspaceId),
      ]);
      setMessages(messageRes.items);
      setUploads(uploadRes.items);
    } catch (err: unknown) {
      console.error("Failed to load conversation:", err);
      setMessages([]);
      setUploads([]);
    } finally {
      setLoadingMessages(false);
    }
  };

  useEffect(() => {
    void loadSessions();
  }, [workspaceId]);

  useEffect(() => {
    if (!activeSessionId) return;
    void loadConversation(activeSessionId);
  }, [activeSessionId, workspaceId]);

  useEffect(() => {
    if (!feedRef.current) return;
    feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [messages]);

  const handleCreateSession = async () => {
    if (!workspaceId) return;
    const title = `Chat ${sessions.length + 1}`;
    const session = await createChatSession({ workspace_id: workspaceId, title });
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setMessages([]);
    setUploads([]);
  };

  const handleUpload = async (files: File[]) => {
    if (!workspaceId || !activeSessionId || files.length === 0) return;
    setUploading(true);
    try {
      for (const file of files) {
        await uploadChatFile(activeSessionId, workspaceId, file);
      }
      const uploadRes = await listChatUploads(activeSessionId, workspaceId);
      setUploads(uploadRes.items);
    } finally {
      setUploading(false);
    }
  };

  const handleSend = async () => {
    if (!workspaceId || !activeSessionId || sending) return;
    const content = prompt.trim();
    if (!content) return;

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
          void loadSessions();
        },
        onError: () => {
          setSending(false);
          setMessages((prev) => prev.filter((msg) => msg.id !== draftId));
        },
      },
    );
  };

  const handleWorkflowApprove = async (artifactId: string) => {
    console.log("Workflow approved:", artifactId);
  };

  const handleWorkflowModify = async (artifactId: string, feedback: string) => {
    if (!workspaceId || !activeSessionId) return;
    setPrompt(`Please modify the workflow: ${feedback}`);
  };

  const handleWorkflowCancel = async (artifactId: string) => {
    console.log("Workflow cancelled:", artifactId);
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
                void loadSessions();
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

