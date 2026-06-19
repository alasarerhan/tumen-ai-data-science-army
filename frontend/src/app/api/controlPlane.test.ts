import { describe, expect, it, vi, beforeEach } from "vitest";
import {
  executeControlPlaneAction,
  getControlPlaneCatalog,
  planControlPlaneAction,
  queryControlPlane,
} from "./controlPlane";
import * as client from "./client";

vi.mock("./client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  qs: (params: Record<string, unknown>) => {
    const p = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") p.set(key, String(value));
    }
    const s = p.toString();
    return s ? `?${s}` : "";
  },
}));

describe("controlPlane API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads the catalog for a workspace", async () => {
    vi.mocked(client.apiGet).mockResolvedValue({ items: [] });

    await getControlPlaneCatalog("ws-1");

    expect(client.apiGet).toHaveBeenCalledWith("/v1/control-plane/catalog?workspace_id=ws-1");
  });

  it("queries the control plane", async () => {
    const body = { workspace_id: "ws-1", query: "platform status", resource_keys: ["runs"] };
    vi.mocked(client.apiPost).mockResolvedValue({ type: "platform_query_result", sections: [] });

    await queryControlPlane(body);

    expect(client.apiPost).toHaveBeenCalledWith("/v1/control-plane/query", body);
  });

  it("plans and executes actions through dedicated endpoints", async () => {
    vi.mocked(client.apiPost).mockResolvedValue({});

    await planControlPlaneAction({ workspace_id: "ws-1", action_name: "runs.cancel", arguments: { run_id: "r1" } });
    await planControlPlaneAction({ workspace_id: "ws-1", query: "cancel run r1" });
    await executeControlPlaneAction({
      workspace_id: "ws-1",
      action_name: "runs.cancel",
      arguments: { run_id: "r1" },
      confirmed: true,
    });

    expect(client.apiPost).toHaveBeenNthCalledWith(1, "/v1/control-plane/actions/plan", {
      workspace_id: "ws-1",
      action_name: "runs.cancel",
      arguments: { run_id: "r1" },
    });
    expect(client.apiPost).toHaveBeenNthCalledWith(2, "/v1/control-plane/actions/plan", {
      workspace_id: "ws-1",
      query: "cancel run r1",
    });
    expect(client.apiPost).toHaveBeenNthCalledWith(3, "/v1/control-plane/actions/execute", {
      workspace_id: "ws-1",
      action_name: "runs.cancel",
      arguments: { run_id: "r1" },
      confirmed: true,
    });
  });
});
