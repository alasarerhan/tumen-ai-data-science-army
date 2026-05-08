import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import PipelineMonitor from "./PipelineMonitor";
import { AuthProvider } from "../context/AuthContext";
import * as runsApi from "../api/runs";
import * as signalsApi from "../api/signals";
import * as logsApi from "../api/logs";
import * as workflowsApi from "../api/workflows";

vi.mock("../api/runs", () => ({
  getRuns: vi.fn(),
}));

vi.mock("../api/workflows", () => ({
  getWorkflows: vi.fn(),
}));

vi.mock("../api/signals", () => ({
  buildSignalStreamUrl: vi.fn(() => "http://test/signals"),
  emitSignal: vi.fn(),
  listSignals: vi.fn(() => Promise.resolve({ items: [] })),
}));

vi.mock("../api/logs", () => ({
  buildRunLogsStreamUrl: vi.fn(() => "http://test/logs"),
}));

vi.mock("../hooks/useEventSource", () => ({
  useEventSource: () => ({
    events: [],
    isStreaming: false,
    error: null,
    clear: vi.fn(),
    reconnect: vi.fn(),
    reconnectAttempts: 0,
  }),
}));

const mockRuns = [
  {
    id: "run-1",
    flow_key: "test-flow",
    status: "running",
    created_at: "2024-01-15T10:00:00Z",
    started_at: "2024-01-15T10:01:00Z",
  },
  {
    id: "run-2",
    flow_key: "another-flow",
    status: "completed",
    created_at: "2024-01-15T09:00:00Z",
    started_at: "2024-01-15T09:01:00Z",
  },
];

function renderPipelineMonitor(initialRoute = "/monitor") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <AuthProvider>
        <Routes>
          <Route path="/monitor" element={<PipelineMonitor />} />
          <Route path="/monitor/:runId" element={<PipelineMonitor />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("PipelineMonitor", () => {
  beforeEach(() => {
    localStorage.setItem("auth_token", "test-token");
    localStorage.setItem("workspace_id", "ws-123");
    vi.mocked(workflowsApi.getWorkflows).mockResolvedValue({
      items: [
        {
          id: "wf-1",
          workspace_id: "ws-123",
          tenant_id: "tenant-1",
          name: "test-flow",
          version: 1,
          status: "published",
          spec: {},
          validation_summary: {
            status: "safe",
            error_count: 0,
            warning_count: 0,
            errors: [],
            warnings: [],
          },
          created_at: null,
          updated_at: null,
        },
        {
          id: "wf-2",
          workspace_id: "ws-123",
          tenant_id: "tenant-1",
          name: "another-flow",
          version: 1,
          status: "published",
          spec: {},
          validation_summary: {
            status: "invalid",
            error_count: 1,
            warning_count: 0,
            errors: ["bad chain"],
            warnings: [],
          },
          created_at: null,
          updated_at: null,
        },
      ],
    });
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("renders pipeline monitor header", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Pipeline Monitor")).toBeInTheDocument();
    });
  });

  it("loads and displays runs list", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("test-flow")).toBeInTheDocument();
      expect(screen.getByText("another-flow")).toBeInTheDocument();
      expect(screen.getAllByText("Chain Safe").length).toBeGreaterThan(0);
      expect(screen.getByText("Invalid Chain")).toBeInTheDocument();
    });
  });

  it("shows loading state while fetching runs", async () => {
    vi.mocked(runsApi.getRuns).mockImplementation(() => new Promise(() => {}));
    renderPipelineMonitor();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("shows error state when runs fetch fails", async () => {
    vi.mocked(runsApi.getRuns).mockRejectedValue(new Error("Failed to load"));
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Failed to load")).toBeInTheDocument();
    });
  });

  it("shows empty state when no runs", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: [] });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("No runs found")).toBeInTheDocument();
    });
  });

  it("selects run from route param", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor("/monitor/run-2");

    await waitFor(() => {
      const runIds = screen.getAllByText("run-2");
      expect(runIds.length).toBeGreaterThan(0);
    });
  });

  it("clicks run to select it", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    vi.mocked(signalsApi.listSignals).mockResolvedValue({ items: [] });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("test-flow")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("another-flow"));

    await waitFor(() => {
      const runIds = screen.getAllByText("run-2");
      expect(runIds.length).toBeGreaterThan(0);
    });
  });

  it("shows run timeline section", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Run Timeline & Live Logs")).toBeInTheDocument();
    });
  });

  it("shows signal controls section", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Signal History & Controls")).toBeInTheDocument();
    });
  });

  it("shows signal type selector", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Send Signal")).toBeInTheDocument();
    });
  });

  it("shows signal history", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    vi.mocked(signalsApi.listSignals).mockResolvedValue({ items: [] });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Signal History")).toBeInTheDocument();
    });
  });

  it("shows no signals message when empty", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    vi.mocked(signalsApi.listSignals).mockResolvedValue({ items: [] });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("No signals yet.")).toBeInTheDocument();
    });
  });

  it("shows existing signals in history", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    vi.mocked(signalsApi.listSignals).mockResolvedValue({
      items: [
        {
          id: "sig-1",
          signal_type: "pause",
          target_step: "step-1",
          note: "Test note",
          created_at: "2024-01-15T10:00:00Z",
        },
      ],
    });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Test note")).toBeInTheDocument();
    });
    const signalTypeBadges = screen.getAllByText("pause");
    expect(signalTypeBadges.length).toBeGreaterThan(0);
  });

  it("refresh button triggers runs reload", async () => {
    vi.mocked(runsApi.getRuns).mockResolvedValue({ items: mockRuns });
    renderPipelineMonitor();

    await waitFor(() => {
      expect(screen.getByText("Refresh")).toBeInTheDocument();
    });

    const initialCallCount = vi.mocked(runsApi.getRuns).mock.calls.length;
    fireEvent.click(screen.getByText("Refresh"));

    await waitFor(() => {
      expect(vi.mocked(runsApi.getRuns).mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });
});
