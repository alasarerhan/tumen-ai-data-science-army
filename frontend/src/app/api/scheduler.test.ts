import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  createScheduledDeployment,
  listScheduledDeployments,
  getWorkflowSchedule,
  pauseScheduledDeployment,
  resumeScheduledDeployment,
  triggerScheduledWorkflow,
} from "./scheduler";
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

describe("scheduler API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe("createScheduledDeployment", () => {
    it("calls POST /v1/workflows/:id/schedule", async () => {
      const mockResponse = {
        deployment_id: "dep-123",
        deployment_name: "Test Deployment",
        cron: "0 0 * * *",
        timezone: "UTC",
        enabled: true,
        workflow_spec_id: "wf-123",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await createScheduledDeployment("wf-123", {
        workspace_id: "ws-123",
        cron: "0 0 * * *",
      });

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/schedule?workspace_id=ws-123",
        { cron: "0 0 * * *", timezone: undefined },
      );
      expect(result).toEqual(mockResponse);
    });

    it("includes timezone when provided", async () => {
      const mockResponse = {
        deployment_id: "dep-123",
        deployment_name: "Test Deployment",
        cron: "0 0 * * *",
        timezone: "America/New_York",
        enabled: true,
        workflow_spec_id: "wf-123",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      await createScheduledDeployment("wf-123", {
        workspace_id: "ws-123",
        cron: "0 0 * * *",
        timezone: "America/New_York",
      });

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/schedule?workspace_id=ws-123",
        { cron: "0 0 * * *", timezone: "America/New_York" },
      );
    });
  });

  describe("listScheduledDeployments", () => {
    it("calls GET /v1/workflows/schedules", async () => {
      const mockResponse = {
        items: [
          {
            deployment_id: "dep-123",
            deployment_name: "Test",
            workflow_spec_id: "wf-123",
            cron: "0 0 * * *",
            timezone: "UTC",
            enabled: true,
            next_run_at: "2024-01-16T00:00:00Z",
            last_run_at: null,
            last_run_status: null,
          },
        ],
      };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await listScheduledDeployments("ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/workflows/schedules?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getWorkflowSchedule", () => {
    it("calls GET /v1/workflows/:id/schedule", async () => {
      const mockResponse = {
        deployment_id: "dep-123",
        deployment_name: "Test",
        workflow_spec_id: "wf-123",
        cron: "0 0 * * *",
        timezone: "UTC",
        enabled: true,
        next_run_at: "2024-01-16T00:00:00Z",
        last_run_at: null,
        last_run_status: null,
      };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getWorkflowSchedule("wf-123", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/schedule?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("pauseScheduledDeployment", () => {
    it("calls POST /v1/workflows/schedules/:id/pause", async () => {
      const mockResponse = {
        deployment_id: "dep-123",
        status: "paused",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await pauseScheduledDeployment("dep-123", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/schedules/dep-123/pause?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("resumeScheduledDeployment", () => {
    it("calls POST /v1/workflows/schedules/:id/resume", async () => {
      const mockResponse = {
        deployment_id: "dep-123",
        status: "active",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await resumeScheduledDeployment("dep-123", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/schedules/dep-123/resume?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("triggerScheduledWorkflow", () => {
    it("calls POST /v1/workflows/:id/trigger without parameters", async () => {
      const mockResponse = {
        flow_run_id: "run-123",
        status: "pending",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await triggerScheduledWorkflow("wf-123", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/trigger?workspace_id=ws-123",
        { parameters: undefined },
      );
      expect(result).toEqual(mockResponse);
    });

    it("calls POST /v1/workflows/:id/trigger with parameters", async () => {
      const mockResponse = {
        flow_run_id: "run-123",
        status: "pending",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const parameters = { input_file: "data.csv", mode: "batch" };
      const result = await triggerScheduledWorkflow("wf-123", "ws-123", parameters);

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/trigger?workspace_id=ws-123",
        { parameters },
      );
      expect(result).toEqual(mockResponse);
    });
  });
});
