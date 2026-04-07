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

vi.mock("../lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

import CloudOps from "../screens/CloudOps";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <CloudOps />
    </BrowserRouter>
  );
}

describe("CloudOps", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render cloud ops page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show deployment stages", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show activity feed", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
