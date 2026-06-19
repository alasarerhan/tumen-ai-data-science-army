import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  getWorkflows,
  getWorkflow,
  createWorkflow,
  publishWorkflow,
  archiveWorkflow,
  getWorkflowVersions,
} from "./workflows";
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

describe("workflows API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe("getWorkflows", () => {
    it("calls GET /v1/workflows with workspace_id", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getWorkflows({ workspace_id: "ws-123" });

      expect(client.apiGet).toHaveBeenCalledWith("/v1/workflows?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });

    it("includes name filter when provided", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      await getWorkflows({ workspace_id: "ws-123", name: "my-workflow" });

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/workflows?workspace_id=ws-123&name=my-workflow",
      );
    });

    it("includes status filter when provided", async () => {
      const mockResponse = { items: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      await getWorkflows({ workspace_id: "ws-123", status: "published" });

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/workflows?workspace_id=ws-123&status=published",
      );
    });
  });

  describe("getWorkflow", () => {
    it("calls GET /v1/workflows/:id with workspace_id", async () => {
      const mockResponse = {
        id: "wf-123",
        name: "Test Workflow",
        version: 1,
        status: "draft",
      };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getWorkflow("wf-123", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith("/v1/workflows/wf-123?workspace_id=ws-123");
      expect(result).toEqual(mockResponse);
    });
  });

  describe("createWorkflow", () => {
    it("calls POST /v1/workflows with body", async () => {
      const mockResponse = {
        id: "wf-123",
        name: "New Workflow",
        version: 1,
        status: "draft",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const body = {
        workspace_id: "ws-123",
        name: "New Workflow",
        spec: { nodes: [], edges: [] },
      };
      const result = await createWorkflow(body);

      expect(client.apiPost).toHaveBeenCalledWith("/v1/workflows", body);
      expect(result).toEqual(mockResponse);
    });

    it("includes publish flag when provided", async () => {
      const mockResponse = {
        id: "wf-123",
        name: "New Workflow",
        version: 1,
        status: "published",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const body = {
        workspace_id: "ws-123",
        name: "New Workflow",
        spec: { nodes: [], edges: [] },
        publish: true,
      };
      await createWorkflow(body);

      expect(client.apiPost).toHaveBeenCalledWith("/v1/workflows", body);
    });
  });

  describe("publishWorkflow", () => {
    it("calls POST /v1/workflows/:id/publish", async () => {
      const mockResponse = {
        id: "wf-123",
        name: "Test Workflow",
        version: 2,
        status: "published",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await publishWorkflow("wf-123", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/publish?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("archiveWorkflow", () => {
    it("calls POST /v1/workflows/:id/archive", async () => {
      const mockResponse = {
        id: "wf-123",
        name: "Test Workflow",
        version: 1,
        status: "archived",
      };
      vi.mocked(client.apiPost).mockResolvedValue(mockResponse);

      const result = await archiveWorkflow("wf-123", "ws-123");

      expect(client.apiPost).toHaveBeenCalledWith(
        "/v1/workflows/wf-123/archive?workspace_id=ws-123",
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("getWorkflowVersions", () => {
    it("calls GET /v1/versioning/workflows/:id/versions", async () => {
      const mockResponse = { versions: [] };
      vi.mocked(client.apiGet).mockResolvedValue(mockResponse);

      const result = await getWorkflowVersions("wf-123", "ws-123");

      expect(client.apiGet).toHaveBeenCalledWith(
        "/v1/versioning/workflows/wf-123/versions?workspace_id=ws-123&limit=10",
      );
      expect(result).toEqual(mockResponse);
    });
  });
});
