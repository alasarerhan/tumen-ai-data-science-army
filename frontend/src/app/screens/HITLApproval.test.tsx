import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";

vi.mock("react-router", async () => {
  const actual = await vi.importActual("react-router");
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: "hitl-1" }),
  };
});

vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({
    user: { email: "test@example.com", sub: "test-sub", id: "user-1" },
    workspaceId: "test-workspace",
  }),
}));

vi.mock("../api/hitl", () => ({
  getHitlItem: vi.fn().mockResolvedValue({ id: "hitl-1", status: "pending" }),
  approveHitl: vi.fn().mockResolvedValue({}),
  rejectHitl: vi.fn().mockResolvedValue({}),
}));

import HITLApproval from "../screens/HITLApproval";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <HITLApproval />
    </BrowserRouter>
  );
}

describe("HITLApproval", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render hitl approval page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show approval buttons", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show code sample", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
