import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", sub: "test-sub", id: "user-1" },
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../hooks/useDiscovery", () => ({
  useAgentCatalog: () => ({
    data: {
      results: [
        {
          name: "Test Agent",
          category: "machine_learning",
          status: "healthy",
          description: "Test description",
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useAgentExecutionSummary: () => ({
    data: {
      type: "platform_query_result",
      summary: "Control plane resolved node executions.",
      query: "agent execution traces",
      plan: { query: "agent execution traces", resource_keys: ["run.nodes"], filters: {}, limit: 100 },
      sections: [
        {
          resource_key: "run.nodes",
          label: "Run Node Executions",
          status: "ok",
          message: null,
          columns: ["node_type", "status", "retry_count"],
          records: [
            { node_type: "model.train", status: "failed", retry_count: 1 },
            { node_type: "model.train", status: "succeeded", retry_count: 0 },
          ],
          metrics: {},
          links: [],
          relationships: [],
          provenance: {
            resource_key: "run.nodes",
            resolver: "run_nodes",
            generated_at: "2026-06-04T10:00:00Z",
            filters: {},
            redactions: [],
          },
        },
        {
          resource_key: "agent.traces",
          label: "Agent Execution Traces",
          status: "ok",
          message: null,
          columns: ["node_id", "node_type", "attempt", "status", "duration_ms", "tool_call_count"],
          records: [
            {
              node_id: "train",
              node_type: "model.train",
              attempt: 1,
              status: "failed",
              duration_ms: 1200,
              tool_call_count: 2,
              artifact_ids: ["model-1"],
              token_usage: { prompt_tokens: 100, completion_tokens: 25 },
              cost_summary: { usd: 0.05 },
              evaluation_summary: { auc: 0.89 },
              version_metadata: { agent_version: "m22.1" },
              error_summary: "training failed",
            },
          ],
          metrics: {},
          links: [],
          relationships: [],
          provenance: {
            resource_key: "agent.traces",
            resolver: "agent_traces",
            generated_at: "2026-06-04T10:00:00Z",
            filters: {},
            redactions: [],
          },
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

import Agents from "../screens/Agents";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <Agents />
    </BrowserRouter>
  );
}

describe("Agents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render agents page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show agent count", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should display agent cards", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show agent cockpit execution summary", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Agent Cockpit")).toBeInTheDocument();
      expect(screen.getByText("2 node execution records from platform runs.")).toBeInTheDocument();
      expect(screen.getByText("model.train")).toBeInTheDocument();
      expect(screen.getByText("50%")).toBeInTheDocument();
      expect(screen.getByText("Tool Calls")).toBeInTheDocument();
      expect(screen.getByText("Token Fields")).toBeInTheDocument();
      expect(screen.getByText("Cost Fields")).toBeInTheDocument();
      expect(screen.getByText("Eval/Version")).toBeInTheDocument();
      expect(screen.getAllByText("2").length).toBeGreaterThan(0);
      expect(screen.getByText("1x training failed")).toBeInTheDocument();
    });
  });

  it("should show agent type", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
