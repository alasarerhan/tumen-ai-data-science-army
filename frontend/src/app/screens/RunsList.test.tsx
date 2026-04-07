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
  useTriggerRun: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useRetryRun: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useCancelRun: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
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
