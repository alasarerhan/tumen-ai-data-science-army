import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createChatSession,
  listChatMessages,
  listChatSessions,
  listChatUploads,
  uploadChatFile,
  type ChatMessageDto,
  type ChatSessionDto,
  type ChatUploadDto,
} from "../api/chat";

export function useChatSessions(workspaceId: string | null) {
  return useQuery<{ items: ChatSessionDto[] }>({
    queryKey: ["chat-sessions", workspaceId],
    queryFn: () => listChatSessions(workspaceId!),
    enabled: Boolean(workspaceId),
  });
}

export function useCreateChatSession(workspaceId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (title: string) => createChatSession({ workspace_id: workspaceId!, title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions", workspaceId] });
    },
  });
}

export function useChatMessages(sessionId: string | null, workspaceId: string | null) {
  return useQuery<{ items: ChatMessageDto[] }>({
    queryKey: ["chat-messages", workspaceId, sessionId],
    queryFn: () => listChatMessages(sessionId!, workspaceId!),
    enabled: Boolean(sessionId && workspaceId),
  });
}

export function useChatUploads(sessionId: string | null, workspaceId: string | null) {
  return useQuery<{ items: ChatUploadDto[] }>({
    queryKey: ["chat-uploads", workspaceId, sessionId],
    queryFn: () => listChatUploads(sessionId!, workspaceId!),
    enabled: Boolean(sessionId && workspaceId),
  });
}

export function useUploadChatFiles(sessionId: string | null, workspaceId: string | null) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (files: File[]) => {
      const uploaded: ChatUploadDto[] = [];
      for (const file of files) {
        uploaded.push(await uploadChatFile(sessionId!, workspaceId!, file));
      }
      return uploaded;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-uploads", workspaceId, sessionId] });
    },
  });
}
