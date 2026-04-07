import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  createChatSession,
  listChatSessions,
  getChatSession,
  archiveChatSession,
  listChatMessages,
  sendChatMessage,
  listChatUploads,
} from "./chat";
import * as client from "./client";

vi.mock("./client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiDelete: vi.fn(),
  qs: (params: Record<string, unknown>) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
    }
    const s = p.toString();
    return s ? `?${s}` : "";
  },
}));

describe("chat API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("createChatSession", () => {
    it("calls POST /v1/chat/sessions with body", async () => {
      const mockResponse = {
        id: "session-1",
        title: "Test Chat",
        status: "active",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await createChatSession({
        workspace_id: "ws-123",
        title: "Test Chat",
      });

      expect(client.apiPost).toHaveBeenCalledWith("/v1/chat/sessions", {
        workspace_id: "ws-123",
        title: "Test Chat",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("listChatSessions", () => {
    it("calls GET /v1/chat/sessions with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await listChatSessions("ws-123");

      expect(client.apiGet).toHaveBeenCalledWith("/v1/chat/sessions?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getChatSession", () => {
    it("calls GET /v1/chat/sessions/:id with workspace_id", async () => {
      const mockResponse = {
        id: "session-1",
        title: "Test Chat",
        status: "active",
      };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getChatSession("session-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/chat/sessions/session-1?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("archiveChatSession", () => {
    it("calls DELETE /v1/chat/sessions/:id with workspace_id", async () => {
      const mockResponse = {
        id: "session-1",
        status: "archived",
      };
      vi.mocked(client.apiDelete).mockResolvedValue(mockResponse);

      const result = await archiveChatSession("session-1", "ws-123");

      expect(client.apiDelete).toHaveBeenCalledWith(
        "/v1/chat/sessions/session-1?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("listChatMessages", () => {
    it("calls GET /v1/chat/sessions/:id/messages with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await listChatMessages("session-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/chat/sessions/session-1/messages?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("sendChatMessage", () => {
    it("calls POST /v1/chat/sessions/:id/messages with body", async () => {
      const mockResponse = {
        id: "msg-1",
        role: "user",
        content: "Hello",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await sendChatMessage("session-1", {
        workspace_id: "ws-123",
        content: "Hello",
      });

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/chat/sessions/session-1/messages",
        { workspace_id: "ws-123", content: "Hello" },
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("listChatUploads", () => {
    it("calls GET /v1/chat/sessions/:id/uploads with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await listChatUploads("session-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/chat/sessions/session-1/uploads?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });
});
