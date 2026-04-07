import { describe, it, expect, vi, beforeEach } from "vitest";
import { emitSignal, listSignals, buildSignalStreamUrl } from "./signals";
import * as client from "./client";

vi.mock("./client", () => ({
  BASE_URL: "http://localhost:8000",
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

describe("signals API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("emitSignal", () => {
    it("calls POST /v1/runs/:id/signals with body", async () => {
      const mockResponse = {
        id: "signal-1",
        signal_type: "pause",
        workflow_run_id: "run-1",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await emitSignal("run-1", {
        workspace_id: "ws-123",
        signal_type: "pause",
        target_step: "step-1",
      });

      expect(client.apiPost).toHaveBeenCalledWith("/v1/runs/run-1/signals", {
        workspace_id: "ws-123",
        signal_type: "pause",
        target_step: "step-1",
      });
      expect(result).toEqual(mockResponse);
    });

    it("works with minimal body", async () => {
      const mockResponse = {
        id: "signal-1",
        signal_type: "cancel",
        workflow_run_id: "run-1",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await emitSignal("run-1", {
        workspace_id: "ws-123",
        signal_type: "cancel",
      });

      expect(client.apiPost).toHaveBeenCalledWith("/v1/runs/run-1/signals", {
        workspace_id: "ws-123",
        signal_type: "cancel",
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe("listSignals", () => {
    it("calls GET /v1/runs/:id/signals with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await listSignals("run-1", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/runs/run-1/signals?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("buildSignalStreamUrl", () => {
    it("builds correct URL without last_event_id", () => {
      const url = buildSignalStreamUrl("run-1", "ws-123");

      expect(url).toBe(
        "http://localhost:8000/v1/runs/run-1/signals/stream?workspace_id=ws-123",
      );
    });

    it("builds correct URL with last_event_id", () => {
      const url = buildSignalStreamUrl("run-1", "ws-123", "event-123");

      expect(url).toContain("workspace_id=ws-123");
      expect(url).toContain("last_event_id=event-123");
    });
  });
});
