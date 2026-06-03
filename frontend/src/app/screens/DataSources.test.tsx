import { describe, it, expect, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { BrowserRouter } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <DataSources />
      </BrowserRouter>
    </QueryClientProvider>
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

  it("should render SQL Server structured connection fields", async () => {
    renderWithProviders();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /add data source/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /add data source/i }));
    fireEvent.click(screen.getByRole("button", { name: /sql server/i }));
    fireEvent.click(screen.getByRole("button", { name: /continue/i }));

    expect(screen.getByText("SQL Server Details")).toBeInTheDocument();
    expect(screen.getByText("Host")).toBeInTheDocument();
    expect(screen.getByText("Database")).toBeInTheDocument();
    expect(screen.getByText("Username")).toBeInTheDocument();
    expect(screen.getByText("Password")).toBeInTheDocument();
    expect(screen.getByText("Encrypt connection")).toBeInTheDocument();
    expect(screen.getByText("Trust server certificate")).toBeInTheDocument();
  });
});
