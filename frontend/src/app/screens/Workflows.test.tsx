import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockNavigate = vi.fn();

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
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
          name: "Test Workflow",
          status: "published",
          spec: { description: "Test description" },
          validation_summary: {
            status: "safe",
            error_count: 0,
            warning_count: 0,
            errors: [],
            warnings: [],
          },
          version: 1,
          updated_at: new Date().toISOString(),
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useArchiveWorkflow: vi.fn().mockReturnValue({
    mutateAsync: vi.fn().mockResolvedValue({}),
  }),
}));

vi.mock("../hooks/useSchedules", () => ({
  useSchedules: vi.fn().mockReturnValue({
    data: { items: [] },
  }),
  usePauseSchedule: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useResumeSchedule: vi.fn().mockReturnValue({ mutateAsync: vi.fn().mockResolvedValue({}) }),
}));

vi.mock("../utils/time", () => ({
  formatRelativeTime: vi.fn(() => "2 hours ago"),
}));

vi.mock("../lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

import Workflows from "../screens/Workflows";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Workflows />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("Workflows", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render workflows header", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show new workflow button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /new workflow/i })).toBeInTheDocument();
    });
  });

  it("should show search input", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search workflows/i)).toBeInTheDocument();
    });
  });

  it("should display workflow list", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Test Workflow")).toBeInTheDocument();
    });
  });

  it("should navigate to new workflow on button click", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /new workflow/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /new workflow/i }));

    expect(mockNavigate).toHaveBeenCalledWith("/workflows/new/designer");
  });

  it("should filter workflows by search", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Test Workflow")).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search workflows/i);
    fireEvent.change(searchInput, { target: { value: "nonexistent" } });

    await waitFor(() => {
      expect(screen.queryByText("Test Workflow")).not.toBeInTheDocument();
    });
  });
});
