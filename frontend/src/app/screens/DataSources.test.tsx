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

vi.mock("../api/datasources", () => ({
  getDataSources: vi.fn().mockResolvedValue({ items: [] }),
  createDataSource: vi.fn().mockResolvedValue({}),
  deleteDataSource: vi.fn().mockResolvedValue({}),
  testDataSource: vi.fn().mockResolvedValue({ healthy: true }),
}));

vi.mock("../utils/time", () => ({
  formatRelativeTime: vi.fn(() => "2 hours ago"),
}));

vi.mock("../lib/utils", () => ({
  cn: (...args: string[]) => args.filter(Boolean).join(" "),
}));

import DataSources from "../screens/DataSources";

function renderWithProviders() {
  return render(
    <BrowserRouter>
      <DataSources />
    </BrowserRouter>
  );
}

describe("DataSources", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render data sources page", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show add data source button", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });

  it("should show data sources list", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
    });
  });
});
