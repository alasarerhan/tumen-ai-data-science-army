import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { getArtifacts, type Artifact } from "../api/artifacts";
import Reports from "../screens/Reports";

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

vi.mock("../api/artifacts", () => ({
  getArtifacts: vi.fn(),
}));

const artifactItems: Artifact[] = [
  {
    id: "dataset-1",
    workspace_id: "test-workspace",
    tenant_id: "tenant-1",
    workflow_run_id: "run-1",
    kind: "dataset",
    uri: "/artifacts/input.csv",
    produced_by_node_id: "ingest",
    parent_artifact_ids: [],
    created_at: "2026-06-01T10:00:00Z",
  },
  {
    id: "model-1",
    workspace_id: "test-workspace",
    tenant_id: "tenant-1",
    workflow_run_id: "run-1",
    kind: "model",
    uri: "/artifacts/model.pkl",
    produced_by_node_id: "train",
    parent_artifact_ids: ["dataset-1"],
    created_at: "2026-06-01T10:10:00Z",
  },
  {
    id: "metrics-1",
    workspace_id: "test-workspace",
    tenant_id: "tenant-1",
    workflow_run_id: "run-1",
    kind: "metrics",
    uri: "/artifacts/metrics.json",
    produced_by_node_id: "evaluate",
    parent_artifact_ids: ["model-1"],
    created_at: "2026-06-01T10:20:00Z",
  },
  {
    id: "report-1",
    workspace_id: "test-workspace",
    tenant_id: "tenant-1",
    workflow_run_id: "run-1",
    kind: "strategy_report",
    uri: "/reports/test.pdf",
    produced_by_node_id: "report",
    parent_artifact_ids: ["metrics-1"],
    created_at: "2026-06-01T10:30:00Z",
  },
];

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <Reports />
    </BrowserRouter>,
  );
}

describe("Reports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getArtifacts).mockResolvedValue({ items: artifactItems });
  });

  it("loads artifacts for the workspace output board", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(getArtifacts).toHaveBeenCalledWith({ workspace_id: "test-workspace", limit: 100 });
    });
    expect(screen.getByRole("heading", { level: 1, name: "Reports & Artifacts" })).toBeInTheDocument();
    expect(screen.getByText("Pipeline Output Board")).toBeInTheDocument();
    expect(screen.getAllByText("model.pkl").length).toBeGreaterThan(0);
    expect(screen.getAllByText("metrics.json").length).toBeGreaterThan(0);
  });

  it("shows artifact lineage edges and source artifacts", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByText("Artifact Lineage Graph")).toBeInTheDocument();
    });
    expect(screen.getAllByText("input.csv").length).toBeGreaterThan(0);
    expect(screen.getByText("model via train")).toBeInTheDocument();
    expect(screen.getByText("metrics via evaluate")).toBeInTheDocument();
    expect(screen.getByText("strategy report via report")).toBeInTheDocument();
  });

  it("keeps report cards for report artifacts", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getAllByText("test.pdf").length).toBeGreaterThan(0);
    });
    expect(screen.getByText("strategy_report")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Read Report/i })).toBeInTheDocument();
  });
});
