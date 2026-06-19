import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", sub: "test-sub", id: "user-1" },
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../api/modelops", () => ({
  getModelOpsSummary: vi.fn().mockResolvedValue({
    registry: [
      {
        model_id: "model-1",
        version: "artifact-model-1",
        stage: "candidate",
        artifact_id: "model-1",
        workflow_run_id: "run-1",
        produced_by_node_id: "train",
        parent_artifact_ids: [],
        uri_scheme: "s3",
        created_at: "2026-06-04T10:00:00Z",
        approval_state: "not_reviewed",
        deployment_state: "not_deployed",
        monitoring_status: "linked",
        latest_metric_artifact_ids: ["metric-1"],
        drift_status: "warning",
        performance_status: "ok",
        retrain_candidate: true,
      },
    ],
    monitors: [
      {
        monitor_id: "metric-1",
        artifact_id: "metric-1",
        kind: "drift_report",
        workflow_run_id: "run-1",
        produced_by_node_id: "evaluate",
        parent_artifact_ids: ["model-1"],
        uri_scheme: "local",
        created_at: "2026-06-04T10:02:00Z",
        freshness: "snapshot",
        drift_status: "warning",
        performance_status: "ok",
        alert_policy: "not_configured",
      },
    ],
    retrain_candidates: [
      {
        model_id: "model-1",
        version: "artifact-model-1",
        reason: "drift_or_performance_signal",
        drift_status: "warning",
        performance_status: "ok",
        linked_monitor_ids: ["metric-1"],
        suggested_workflow: "retrain_from_latest_data",
        action_state: "plan_required",
      },
    ],
    metrics: {
      registered_models: 1,
      monitor_snapshots: 1,
      retrain_candidates: 1,
      deployments: 0,
    },
    status: {
      registry: "artifact_backed",
      monitoring: "artifact_backed",
      deployment: "not_configured",
      retraining: "candidate_detection",
    },
  }),
}));

vi.mock("../utils/time", () => ({
  formatRelativeTime: vi.fn(() => "2 minutes ago"),
}));

import ModelOps from "../screens/ModelOps";

function renderWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ModelOps />
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("ModelOps", () => {
  it("renders artifact-backed registry, monitoring, and retrain candidates", async () => {
    renderWithProviders();

    expect(await screen.findByRole("heading", { level: 1, name: "Model Registry & Monitoring" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("artifact-model-1 / candidate").length).toBeGreaterThan(0);
      expect(screen.getByText("drift_report / snapshot")).toBeInTheDocument();
      expect(screen.getByText("retrain_from_latest_data")).toBeInTheDocument();
      expect(screen.getAllByText("not_configured").length).toBeGreaterThan(0);
    });
  });
});
