import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockNavigate = vi.fn();

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ id: "wf-1" }),
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", sub: "test-sub", id: "user-1" },
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../api/workflows", () => ({
  getWorkflow: vi.fn().mockResolvedValue({
    id: "wf-1",
    workspace_id: "test-workspace",
    tenant_id: "tenant-1",
    name: "Real Workflow",
    version: 2,
    status: "published",
    spec: {
      description: "Loaded from API",
      steps: [
        { id: "load", tool: "data_load" },
        { id: "clean", tool: "data_clean", depends_on: ["load"] },
      ],
    },
    validation_summary: {
      status: "safe",
      error_count: 0,
      warning_count: 0,
      errors: [],
      warnings: [],
    },
    created_at: "2026-06-04T09:00:00Z",
    updated_at: "2026-06-04T10:00:00Z",
  }),
  getWorkflowVersions: vi.fn().mockResolvedValue({
    versions: [
      {
        id: "version-1",
        workflow_id: "wf-1",
        version: 2,
        spec: {},
        changelog: "Published real API version",
        status: "published",
        created_at: "2026-06-04T10:00:00Z",
        published_at: "2026-06-04T10:00:00Z",
        created_by: "user-1",
      },
    ],
  }),
}));

vi.mock("../utils/time", () => ({
  formatRelativeTime: vi.fn(() => "2 hours ago"),
}));

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <WorkflowDetail />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

import WorkflowDetail from "../screens/WorkflowDetail";

describe("WorkflowDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the real workflow spec from the API", async () => {
    renderWithProviders();

    expect(await screen.findByText("Real Workflow")).toBeInTheDocument();
    expect(screen.getByDisplayValue(/Loaded from API/)).toBeInTheDocument();
    expect(screen.getByText("workflow.spec.json")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /read-only/i })).toBeDisabled();
  });

  it("renders real version history and keeps restore disabled", async () => {
    renderWithProviders();

    await screen.findByText("Real Workflow");
    fireEvent.click(screen.getByRole("button", { name: /version history/i }));

    await waitFor(() => {
      expect(screen.getByText("Published real API version")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /restore/i })).toBeDisabled();
  });
});
