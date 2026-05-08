import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: "run-1" }),
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", sub: "test-sub", id: "user-1" },
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../hooks/useWorkflows", () => ({
  useWorkflows: vi.fn().mockReturnValue({
    data: {
      items: [
        {
          id: "wf-1",
          name: "test-flow",
          validation_summary: {
            status: "advisory",
            error_count: 0,
            warning_count: 1,
            errors: [],
            warnings: ["EDA -> Data Cleaning is advisory."],
          },
        },
      ],
    },
    isLoading: false,
  }),
}));

vi.mock("../api/runs", () => ({
  getRun: vi.fn().mockResolvedValue({
    id: "run-1",
    workspace_id: "test-workspace",
    tenant_id: "tenant-1",
    status: "COMPLETED",
    flow_key: "test-flow",
    prefect_flow_run_id: "prefect-run-1",
    parameters: { dataset_name: "Revenue mart", horizon_days: 30 },
    created_at: "2026-04-14T09:00:00Z",
    updated_at: "2026-04-14T09:10:00Z",
    started_at: "2026-04-14T09:01:00Z",
    finished_at: "2026-04-14T09:10:00Z",
  }),
  getRuns: vi.fn().mockResolvedValue({ items: [] }),
  cancelRun: vi.fn().mockResolvedValue({}),
  retryRun: vi.fn().mockResolvedValue({}),
  buildPrefectRunUrl: vi.fn(() => "https://prefect.example/flow-runs/flow-run/prefect-run-1"),
}));

vi.mock("../api/artifacts", () => ({
  getArtifacts: vi.fn().mockResolvedValue({
    items: [
      {
        id: "artifact-1",
        workspace_id: "test-workspace",
        tenant_id: "tenant-1",
        workflow_run_id: "run-1",
        kind: "strategy_report",
        uri: "s3://reports/report.md",
        created_at: "2026-04-14T09:10:00Z",
      },
    ],
  }),
  getArtifactAccess: vi.fn().mockResolvedValue({ url: "http://test.com" }),
}));

vi.mock("../api/logs", () => ({
  buildRunLogsStreamUrl: vi.fn(() => "http://test.com/logs"),
}));

vi.mock("../hooks/useEventSource", () => ({
  useEventSource: vi.fn().mockReturnValue({
    events: [],
    isStreaming: false,
    error: null,
    clear: vi.fn(),
    reconnect: vi.fn(),
    lastEventId: null,
    reconnectAttempts: 0,
  }),
}));

vi.mock("../utils/time", () => ({
  formatDuration: vi.fn(() => "1h 30m"),
  formatRelativeTime: vi.fn(() => "2 hours ago"),
}));

import RunDetail from "../screens/RunDetail";

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <RunDetail />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("RunDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render run detail page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Re-run")).toBeInTheDocument();
    });
  });

  it("should show tabs", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Overview")).toBeInTheDocument();
    });
  });

  it("should show logs tab", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Logs")).toBeInTheDocument();
    });
  });

  it("should show artifacts tab", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Artifacts")).toBeInTheDocument();
    });
  });

  it("should switch tabs on click", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Logs")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Logs"));
  });

  it("renders Prefect deep link when a flow run id exists", async () => {
    renderWithProviders();

    expect(await screen.findByLabelText("Open Prefect run")).toHaveAttribute(
      "href",
      "https://prefect.example/flow-runs/flow-run/prefect-run-1",
    );
  });

  it("builds a strategy readout from run metadata and artifacts", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Strategy Report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Strategy Report"));

    expect(await screen.findByText("Strategy Readout")).toBeInTheDocument();
    expect(
      screen.getByText("Execution completed and outputs are ready for review."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Artifacts: 1 strategy_report/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Dataset Name: Revenue mart/i)).toHaveLength(2);
    expect(screen.getByText(/Source workflow status: Advisory Chain/i)).toBeInTheDocument();
  });

  it("shows source workflow validation details on overview", async () => {
    renderWithProviders();

    expect(await screen.findByText("Source Workflow Validation")).toBeInTheDocument();
    expect(screen.getByText("Advisory Chain")).toBeInTheDocument();
    expect(screen.getByText("EDA -> Data Cleaning is advisory.")).toBeInTheDocument();
  });
});
