import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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

vi.mock("../hooks/useRuns", () => ({
  useRuns: vi.fn().mockReturnValue({
    data: { items: [{ id: "run-1", status: "success", flow_key: "test-flow" }] },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRunNodesForRuns: vi.fn().mockReturnValue([
    {
      data: {
        items: [
          {
            id: "node-exec-1",
            tenant_id: "tenant-1",
            workspace_id: "test-workspace",
            workflow_run_id: "run-1",
            node_id: "train",
            node_type: "model.train",
            status: "succeeded",
            inputs: {},
            outputs: {},
            logs: [],
            error: null,
            retry_count: 1,
            produced_artifact_ids: ["artifact-1", "artifact-2"],
            started_at: "2026-06-04T10:00:00Z",
            finished_at: "2026-06-04T10:05:00Z",
            created_at: "2026-06-04T10:00:00Z",
            updated_at: "2026-06-04T10:05:00Z",
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
    },
  ]),
  useTriggerRun: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useRetryRun: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useCancelRun: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
}));

vi.mock("../hooks/useWorkflows", () => ({
  useWorkflows: vi.fn().mockReturnValue({
    data: {
      items: [
        {
          id: "wf-1",
          name: "test-flow",
          validation_summary: { status: "advisory", error_count: 0, warning_count: 1, errors: [], warnings: ["warn"] },
        },
      ],
    },
  }),
}));

vi.mock("../utils/time", () => ({
  formatDuration: vi.fn(() => "1h 30m"),
  formatRelativeTime: vi.fn(() => "2 hours ago"),
}));

vi.mock("../lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

import RunsList from "../screens/RunsList";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RunsList />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("RunsList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render runs list page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show search input", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });

  it("should show trigger run button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /trigger/i })).toBeInTheDocument();
    });
  });

  it("should display runs table", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("test-flow")).toBeInTheDocument();
      expect(screen.getByText("Advisory Chain")).toBeInTheDocument();
    });
  });

  it("renders workflow run matrix with node execution details", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Workflow Run Matrix")).toBeInTheDocument();
      expect(screen.getByText("model.train")).toBeInTheDocument();
      expect(screen.getByText("R1 / A2")).toBeInTheDocument();
    });
  });

  it("should filter runs by search", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("test-flow")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search/i);
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });

    await waitFor(() => {
      expect(screen.queryByText("test-flow")).not.toBeInTheDocument();
    });
  });
});
