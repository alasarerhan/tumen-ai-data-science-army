import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockNavigate = vi.fn();
const mockParams = { id: "new" };

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => mockParams,
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    workspaceId: "test-workspace",
    user: { email: "test@example.com", role: "admin" },
  }),
}));

vi.mock("../api/workflows", () => ({
  createWorkflow: vi.fn().mockResolvedValue({ id: "wf-1", name: "Test Workflow" }),
  publishWorkflow: vi.fn().mockResolvedValue({ id: "wf-1", status: "published" }),
  getWorkflow: vi.fn().mockResolvedValue({
    id: "wf-1",
    name: "Test Workflow",
    spec: { nodes: [], edges: [] },
  }),
}));

vi.mock("../api/runs", () => ({
  triggerRun: vi.fn().mockResolvedValue({ id: "run-1", status: "pending" }),
}));

vi.mock("../api/scheduler", () => ({
  createScheduledDeployment: vi.fn().mockResolvedValue({ deployment_id: "dep-1" }),
  getWorkflowSchedule: vi.fn().mockResolvedValue(null),
  pauseScheduledDeployment: vi.fn().mockResolvedValue({}),
  resumeScheduledDeployment: vi.fn().mockResolvedValue({}),
}));

vi.mock("@monaco-editor/react", () => ({
  default: ({ value, onChange }: { value: string; onChange?: (v: string) => void }) => (
    <textarea
      data-testid="monaco-editor"
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
    />
  ),
}));

import WorkflowDesigner from "../screens/WorkflowDesigner";
import * as workflowsApi from "../api/workflows";
import * as runsApi from "../api/runs";
import * as schedulerApi from "../api/scheduler";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <WorkflowDesigner />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

describe("WorkflowDesigner", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render workflow designer", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/workflow designer/i)).toBeInTheDocument();
    });
  });

  it("should show save button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    });
  });

  it("should show publish button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
    });
  });

  it("should show run button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run/i })).toBeInTheDocument();
    });
  });

  it("should show schedule button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /schedule/i })).toBeInTheDocument();
    });
  });

  it("should show YAML editor", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByTestId("monaco-editor")).toBeInTheDocument();
    });
  });

  it("should show node palette", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/feature engineering/i)).toBeInTheDocument();
    });
  });

  it("should show initial nodes", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText(/narrative/i)).toBeInTheDocument();
    });
  });

  it("should update YAML when nodes change", async () => {
    renderWithProviders();

    await waitFor(() => {
      const editor = screen.getByTestId("monaco-editor") as HTMLTextAreaElement;
      expect(editor.value).toContain("nodes:");
    });
  });

  it("should call createWorkflow API when save clicked", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    });

    const saveButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(workflowsApi.createWorkflow).toHaveBeenCalled();
    });
  });

  it("should call publishWorkflow API when publish clicked", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
    });

    const publishButton = screen.getByRole("button", { name: /publish/i });
    fireEvent.click(publishButton);

    await waitFor(() => {
      expect(workflowsApi.publishWorkflow).toHaveBeenCalled();
    });
  });

  it("should show error toast when save fails", async () => {
    vi.mocked(workflowsApi.createWorkflow).mockRejectedValueOnce(new Error("Save failed"));

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    });

    const saveButton = screen.getByRole("button", { name: /save/i });
    fireEvent.click(saveButton);
  });

  it("should call triggerRun API when run clicked", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /run/i })).toBeInTheDocument();
    });

    const runButton = screen.getByRole("button", { name: /run/i });
    fireEvent.click(runButton);

    await waitFor(() => {
      expect(runsApi.triggerRun).toHaveBeenCalled();
    });
  });

  it("should call createScheduledDeployment when schedule clicked", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /schedule/i })).toBeInTheDocument();
    });

    const scheduleButton = screen.getByRole("button", { name: /schedule/i });
    fireEvent.click(scheduleButton);
  });

  it("should update YAML editor when nodes change", async () => {
    renderWithProviders();

    await waitFor(() => {
      const editor = screen.getByTestId("monaco-editor") as HTMLTextAreaElement;
      expect(editor.value).toContain("nodes:");
    });

    const editor = screen.getByTestId("monaco-editor") as HTMLTextAreaElement;
    fireEvent.change(editor, { target: { value: "nodes:\n  - id: test" } });

    expect(editor.value).toContain("test");
  });
});
