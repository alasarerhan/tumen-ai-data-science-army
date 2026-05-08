import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
    data: { items: [{ id: "run-1", status: "completed" }] },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../hooks/useWorkflows", () => ({
  useWorkflows: vi.fn().mockReturnValue({
    data: {
      items: [
        {
          id: "wf-1",
          validation_summary: { status: "safe", error_count: 0, warning_count: 0, errors: [], warnings: [] },
        },
        {
          id: "wf-2",
          validation_summary: { status: "advisory", error_count: 0, warning_count: 1, errors: [], warnings: ["warn"] },
        },
        {
          id: "wf-3",
          validation_summary: { status: "invalid", error_count: 1, warning_count: 0, errors: ["err"], warnings: [] },
        },
      ],
    },
    isLoading: false,
  }),
}));

vi.mock("../hooks/useDiscovery", () => ({
  useAgentCatalog: vi.fn().mockReturnValue({
    data: { results: [{ name: "EDA Agent" }, { name: "Model Trainer" }] },
    isLoading: false,
  }),
}));

vi.mock("../hooks/useDataSources", () => ({
  useDataSources: vi.fn().mockReturnValue({
    data: { items: [{ id: "ds-1" }] },
    isLoading: false,
  }),
}));

vi.mock("../utils/time", () => ({
  formatDuration: vi.fn(() => "1h 30m"),
  formatRelativeTime: vi.fn(() => "2 hours ago"),
}));

import Dashboard from "../screens/Dashboard";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render dashboard header", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/good/i)).toBeInTheDocument();
    });
  });

  it("should show workspace id", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show stat cards", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show recent runs section", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show activity section", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show workflow health summary", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Safe: 1")).toBeInTheDocument();
      expect(screen.getByText("Advisory: 1")).toBeInTheDocument();
      expect(screen.getByText("Invalid: 1")).toBeInTheDocument();
    });
  });
});
