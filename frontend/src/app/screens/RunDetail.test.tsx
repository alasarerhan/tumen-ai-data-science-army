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

vi.mock("../api/runs", () => ({
  getRun: vi.fn().mockResolvedValue({ id: "run-1", status: "running", flow_key: "test-flow" }),
  getRuns: vi.fn().mockResolvedValue({ items: [] }),
  cancelRun: vi.fn().mockResolvedValue({}),
  retryRun: vi.fn().mockResolvedValue({}),
}));

vi.mock("../api/artifacts", () => ({
  getArtifacts: vi.fn().mockResolvedValue({ items: [] }),
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

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders() {
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
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
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
});
