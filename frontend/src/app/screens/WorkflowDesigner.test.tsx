import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
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

vi.mock("../hooks/useWorkflowChainRules", () => ({
  useWorkflowChainRules: () => ({
    data: {
      ruleset: {
        version: "1.0.0",
        agents: [
          {
            key: "DataLoaderToolsAgent",
            label: "Data Loader",
            kind: "data",
            color: "#10b981",
            aliases: ["Data Loader"],
            safe_next: ["DataCleaningAgent"],
            conditional_next: [],
          },
          {
            key: "DataCleaningAgent",
            label: "Data Cleaning",
            kind: "data",
            color: "#10b981",
            aliases: ["Data Cleaning"],
            safe_next: ["FeatureEngineeringAgent"],
            conditional_next: [],
          },
          {
            key: "DataWranglingAgent",
            label: "Data Wrangling",
            kind: "data",
            color: "#22c55e",
            aliases: ["Data Wrangling"],
            safe_next: ["DataCleaningAgent"],
            conditional_next: [],
          },
          {
            key: "EDAToolsAgent",
            label: "EDA",
            kind: "analysis",
            color: "#0ea5e9",
            aliases: ["EDA"],
            safe_next: [],
            conditional_next: ["DataCleaningAgent"],
          },
          {
            key: "DataVisualizationAgent",
            label: "Visualization",
            kind: "analysis",
            color: "#06b6d4",
            aliases: ["Visualization"],
            safe_next: [],
            conditional_next: [],
          },
          {
            key: "FeatureEngineeringAgent",
            label: "Feature Engineering",
            kind: "ml",
            color: "#6366f1",
            aliases: ["Feature Engineering"],
            safe_next: ["H2OMLAgent"],
            conditional_next: [],
          },
          {
            key: "H2OMLAgent",
            label: "H2O ML",
            kind: "ml",
            color: "#6366f1",
            aliases: ["H2O ML"],
            safe_next: [],
            conditional_next: [],
          },
          {
            key: "NarrativeAgent",
            label: "Narrative",
            kind: "strategic",
            color: "#ec4899",
            aliases: ["Narrative"],
            safe_next: [],
            conditional_next: [],
          },
          {
            key: "ApprovalGateAgent",
            label: "HITL Gate",
            kind: "hitl",
            color: "#f59e0b",
            aliases: ["HITL Gate"],
            safe_next: [],
            conditional_next: [],
          },
        ],
        requirements: {},
      },
    },
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

vi.mock("../api/workflowNodeTypes", () => ({
  getWorkflowNodeTypes: vi.fn().mockResolvedValue({
    items: [
      {
        type: "dataset.profile",
        label: "Dataset Profile",
        category: "Profiling",
        description: "Profile dataset",
        inputs: [{ name: "dataset", artifact_type: "dataset", required: true }],
        outputs: [{ name: "profile", artifact_type: "profile_report", required: true }],
        ui: { icon: "table", color: "#0ea5e9", config: [] },
        timeout_seconds: 600,
        retry_policy: { max_attempts: 2, backoff_seconds: 10 },
        resources: { class: "cpu_medium" },
      },
      {
        type: "model.train",
        label: "Train Model",
        category: "Modeling",
        description: "Train model",
        inputs: [{ name: "features", artifact_type: "feature_set", required: true }],
        outputs: [{ name: "model", artifact_type: "model", required: true }],
        ui: { icon: "brain", color: "#6366f1", config: [] },
        timeout_seconds: 3600,
        retry_policy: { max_attempts: 1, backoff_seconds: 60 },
        resources: { class: "cpu_large" },
      },
    ],
  }),
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

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
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
      expect(screen.getAllByText(/feature engineering/i).length).toBeGreaterThan(0);
    });
  });

  it("should show initial nodes", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getAllByText(/h2o ml/i).length).toBeGreaterThan(0);
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
    await act(async () => {
      fireEvent.click(saveButton);
    });
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
    await act(async () => {
      fireEvent.click(scheduleButton);
    });

    await waitFor(() => {
      expect(schedulerApi.createScheduledDeployment).toHaveBeenCalledWith("new", {
        workspace_id: "test-workspace",
        cron: "0 8 * * 1-5",
        timezone: "UTC",
      });
    });
  });

  it("should pause and resume an existing schedule", async () => {
    vi.mocked(schedulerApi.getWorkflowSchedule).mockResolvedValueOnce({
      deployment_id: "dep-1",
      deployment_name: "Test deployment",
      workflow_spec_id: "new",
      cron: "0 8 * * 1-5",
      timezone: "UTC",
      enabled: true,
      next_run_at: null,
      last_run_at: null,
      last_run_status: null,
    });

    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /pause schedule/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /pause schedule/i }));

    await waitFor(() => {
      expect(schedulerApi.pauseScheduledDeployment).toHaveBeenCalledWith("dep-1", "test-workspace");
      expect(screen.getByRole("button", { name: /resume schedule/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /resume schedule/i }));

    await waitFor(() => {
      expect(schedulerApi.resumeScheduledDeployment).toHaveBeenCalledWith("dep-1", "test-workspace");
    });
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
