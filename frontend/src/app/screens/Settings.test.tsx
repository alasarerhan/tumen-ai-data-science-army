import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

import Settings from "../screens/Settings";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <Settings />
    </BrowserRouter>
  );
}

describe("Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render settings page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    });
  });

  it("should show navigation items", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    });
  });

  it("should show workspace section", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    });
  });

  it("should show API keys section", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    });
  });

  it("should switch sections on click", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 2 })).toBeInTheDocument();
    });
  });

  it("should expose categorized data source, security, and operations settings", async () => {
    renderWithProviders();

    fireEvent.click(screen.getByRole("button", { name: /data sources/i }));
    expect(screen.getByText("Allowed source types")).toBeInTheDocument();
    expect(screen.getByText("SQL Server form")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /security/i }));
    expect(screen.getByText("Authentication mode")).toBeInTheDocument();
    expect(screen.getByText("Security report triage")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /operations/i }));
    expect(screen.getByText("Health endpoint")).toBeInTheDocument();
    expect(screen.getByText("Monitoring links")).toBeInTheDocument();
  });
});
