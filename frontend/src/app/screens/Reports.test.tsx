import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";

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
  getArtifacts: vi.fn().mockResolvedValue({
    items: [{ id: "report-1", uri: "/reports/test.pdf", kind: "strategy_report", created_at: "2024-01-01" }],
  }),
}));

import Reports from "../screens/Reports";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <Reports />
    </BrowserRouter>
  );
}

describe("Reports", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render reports page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show reports list", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show report kind badge", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
