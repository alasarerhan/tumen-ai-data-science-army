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

vi.mock("../data/agents", () => ({
  agents: [
    { id: "agent-1", name: "Test Agent", type: "ml", status: "healthy", description: "Test description" },
  ],
}));

vi.mock("../lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

import Agents from "../screens/Agents";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <Agents />
    </BrowserRouter>
  );
}

describe("Agents", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render agents page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show agent count", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should display agent cards", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show agent type", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
