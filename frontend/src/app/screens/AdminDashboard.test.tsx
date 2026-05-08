import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { BrowserRouter } from "react-router";

const navigateMock = vi.fn();

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "admin@example.com", sub: "admin-sub", id: "user-1" },
    workspaceId: "workspace-1",
    logout: vi.fn(),
  }),
}));

vi.mock("../api/admin", () => ({
  getDlqEvents: vi.fn().mockResolvedValue({ items: [] }),
  getQueueStats: vi.fn().mockResolvedValue({ pending: 1, processing: 0, failed: 0, dlq: 0 }),
  getSchedulerStatus: vi.fn().mockResolvedValue({
    is_leader: false,
    leader_id: null,
    jobs: [],
    restricted: true,
    message: "Scheduler status is restricted to platform operators.",
  }),
  getMemoryStats: vi.fn().mockResolvedValue({
    rss_bytes: 1024,
    vms_bytes: 2048,
    percent: 35,
    available_system_memory: 4096,
    total_system_memory: 8192,
    growth_rate_bytes_per_minute: 0,
    recommendations: [],
  }),
  replayDlqEvent: vi.fn().mockResolvedValue({ status: "replayed", new_event_id: "evt-2" }),
  runArtifactCleanup: vi.fn().mockResolvedValue({
    dry_run: true,
    artifacts_deleted: 3,
    files_deleted: 2,
    bytes_freed: 2048,
    errors: [],
  }),
}));

import AdminDashboard from "../screens/AdminDashboard";

function renderScreen() {
  return render(
    <BrowserRouter>
      <AdminDashboard />
    </BrowserRouter>,
  );
}

describe("AdminDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders restricted scheduler state for tenant admins", async () => {
    renderScreen();

    expect(await screen.findByText("System Health Dashboard")).toBeInTheDocument();
    expect(await screen.findAllByText("Restricted")).not.toHaveLength(0);
    expect(
      await screen.findAllByText("Scheduler status is restricted to platform operators."),
    ).toHaveLength(2);
  });

  it("shows cleanup preview notice when preview action runs", async () => {
    renderScreen();

    const cleanupButton = await screen.findByRole("button", { name: "Preview Cleanup" });
    fireEvent.click(cleanupButton);

    await waitFor(() => {
      expect(
        screen.getByText(
          "Cleanup preview: 3 artifact records and 2 files are eligible for deletion.",
        ),
      ).toBeInTheDocument();
    });
  });
});
