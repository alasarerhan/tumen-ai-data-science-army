import { describe, it, expect, vi, beforeEach } from "vitest";
import { getRuns, getRun, getRunAgentTraces, getRunNodes, triggerRun, cancelRun, retryRun } from "./runs";
import * as client from "./client";

vi.mock("./client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  qs: (params: Record<string, unknown>) => {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
    }
    const s = p.toString();
    return s ? `?${s}` : "";
  },
}));

describe("runs API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getRuns", () => {
    it("calls GET /v1/runs with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getRuns("ws-123");

      expect(client.apiGet).toHaveBeenCalledWith("/v1/runs?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getRun", () => {
    it("calls GET /v1/runs/:id with workspace_id", async () => {
      const mockResponse = {
        id: "run-1",
        status: "running",
        flow_key: "test-flow",
      };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getRun("run-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith("/v1/runs/run-1?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getRunAgentTraces", () => {
    it("calls GET /v1/runs/:id/agent-traces with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getRunAgentTraces("run-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith("/v1/runs/run-1/agent-traces?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getRunNodes", () => {
    it("calls GET /v1/runs/:id/nodes with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getRunNodes("run-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith("/v1/runs/run-1/nodes?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("triggerRun", () => {
    it("calls POST /v1/runs with body", async () => {
      const mockResponse = {
        id: "run-1",
        status: "pending",
        flow_key: "test-flow",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await triggerRun({
        workspace_id: "ws-123",
        flow_key: "test-flow",
        parameters: { threshold: 0.5 },
      });

      expect(client.apiPost).toHaveBeenCalledWith("/v1/runs", {
        workspace_id: "ws-123",
        flow_key: "test-flow",
        parameters: { threshold: 0.5 },
      });
      expect(result).toEqual(mockResponse);
    });

    it("works with minimal body", async () => {
      const mockResponse = {
        id: "run-1",
        status: "pending",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await triggerRun({ workspace_id: "ws-123" });

      expect(client.apiPost).toHaveBeenCalledWith("/v1/runs", {
        workspace_id: "ws-123",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("cancelRun", () => {
    it("calls POST /v1/runs/:id/cancel with workspace_id", async () => {
      const mockResponse = {
        id: "run-1",
        status: "cancelled",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await cancelRun("run-1", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith("/v1/runs/run-1/cancel", {
        workspace_id: "ws-123",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("retryRun", () => {
    it("calls POST /v1/runs/:id/retry with workspace_id", async () => {
      const mockResponse = {
        id: "run-1",
        status: "pending",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await retryRun("run-1", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith("/v1/runs/run-1/retry", {
        workspace_id: "ws-123",
      });
      expect(result).toEqual(mockResponse);
    });
  });
});
